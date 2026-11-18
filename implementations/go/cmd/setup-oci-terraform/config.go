package main

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strconv"
)

// Restore all generated configuration before changing the active state.
func (app *App) loadExistingConfig() error {
	data, err := os.ReadFile("variables.tf")
	if err != nil { return err }
	content := string(data)
	config := &InstanceConfig{AMDMicroBootVolumeSizeGB: 50}
	for name, target := range map[string]*int{
		"amd_micro_instance_count": &config.AMDMicroInstanceCount,
		"amd_micro_boot_volume_size_gb": &config.AMDMicroBootVolumeSizeGB,
		"arm_flex_instance_count": &config.ARMFlexInstanceCount,
	} {
		match := regexp.MustCompile(`(?m)^\s*` + name + `\s*=\s*(\d+)\s*$`).FindStringSubmatch(content)
		if len(match) != 2 { return fmt.Errorf("missing configuration value %s", name) }
		*target, err = strconv.Atoi(match[1])
		if err != nil { return fmt.Errorf("invalid %s: %w", name, err) }
	}
	for name, target := range map[string]interface{}{
		"amd_micro_hostnames": &config.AMDMicroHostnames,
		"arm_flex_hostnames": &config.ARMFlexHostnames,
		"arm_flex_ocpus_per_instance": &config.ARMFlexOCPUsPerInstance,
		"arm_flex_memory_per_instance": &config.ARMFlexMemoryPerInstance,
		"arm_flex_boot_volume_size_gb": &config.ARMFlexBootVolumeSizeGB,
		"arm_block_volume_sizes": &config.ARMFlexBlockVolumes,
	} {
		match := regexp.MustCompile(`(?m)^\s*` + name + `\s*=\s*(\[[^\]\r\n]*\])\s*$`).FindStringSubmatch(content)
		if len(match) != 2 { return fmt.Errorf("missing configuration array %s", name) }
		if err := json.Unmarshal([]byte(match[1]), target); err != nil { return fmt.Errorf("invalid %s: %w", name, err) }
	}
	if err := validateInstanceConfig(config); err != nil { return err }
	app.InstanceConfig = config
	printSuccess(fmt.Sprintf("Loaded configuration: %dx AMD, %dx ARM", config.AMDMicroInstanceCount, config.ARMFlexInstanceCount))
	return nil
}

func sortedInstanceIDs(instances map[string]InstanceInfo) []string {
	ids := make([]string, 0, len(instances))
	for id := range instances { ids = append(ids, id) }
	sort.Strings(ids)
	return ids
}

func (app *App) configureFromExistingInstances() {
	printStatus("Configuring based on existing instances...")
	config := &InstanceConfig{AMDMicroBootVolumeSizeGB: 50}
	for _, id := range sortedInstanceIDs(app.Resources.AMDInstances) {
		config.AMDMicroHostnames = append(config.AMDMicroHostnames, app.Resources.AMDInstances[id].Name)
	}
	config.AMDMicroInstanceCount = len(config.AMDMicroHostnames)
	for _, id := range sortedInstanceIDs(app.Resources.ARMInstances) {
		instance := app.Resources.ARMInstances[id]
		config.ARMFlexHostnames = append(config.ARMFlexHostnames, instance.Name)
		config.ARMFlexOCPUsPerInstance = append(config.ARMFlexOCPUsPerInstance, instance.OCPUs)
		config.ARMFlexMemoryPerInstance = append(config.ARMFlexMemoryPerInstance, instance.Memory)
		config.ARMFlexBootVolumeSizeGB = append(config.ARMFlexBootVolumeSizeGB, 50)
		config.ARMFlexBlockVolumes = append(config.ARMFlexBlockVolumes, 0)
	}
	config.ARMFlexInstanceCount = len(config.ARMFlexHostnames)
	if config.AMDMicroInstanceCount == 0 && config.ARMFlexInstanceCount == 0 {
		_, cpus, memory, storage := app.calculateAvailableResources()
		if app.OCIConfig.UbuntuARMFlexImageOCID != "" && cpus > 0 && memory > 0 && storage >= FreeTierMinBootVolumeGB {
			config.ARMFlexInstanceCount = 1
			config.ARMFlexOCPUsPerInstance = []int{cpus}
			config.ARMFlexMemoryPerInstance = []int{memory}
			config.ARMFlexBootVolumeSizeGB = []int{storage}
			config.ARMFlexHostnames = []string{"arm-instance-1"}
			config.ARMFlexBlockVolumes = []int{0}
		}
	}
	app.InstanceConfig = config
}

func nonNegative(value int) int {
	if value < 0 { return 0 }
	return value
}

func lesser(a, b int) int {
	if a < b { return a }
	return b
}

func (app *App) calculateAvailableResources() (int, int, int, int) {
	usedOCPUs, usedMemory, usedStorage := 0, 0, 0
	for _, instance := range app.Resources.ARMInstances {
		usedOCPUs += instance.OCPUs
		usedMemory += instance.Memory
	}
	for _, volume := range app.Resources.BootVolumes { usedStorage += volume.Size }
	for _, volume := range app.Resources.BlockVolumes { usedStorage += volume.Size }
	return nonNegative(FreeTierMaxAMDInstances-len(app.Resources.AMDInstances)),
		nonNegative(FreeTierMaxARMOCPUs-usedOCPUs), nonNegative(FreeTierMaxARMMemoryGB-usedMemory),
		nonNegative(FreeTierMaxStorageGB-usedStorage)
}

func (app *App) promptConfiguration() error {
	printHeader("INSTANCE CONFIGURATION")
	amd, cpus, memory, storage := app.calculateAvailableResources()
	fmt.Printf("Available: %d AMD instances, %d ARM OCPUs, %dGB RAM, %dGB storage\n", amd, cpus, memory, storage)
	hasExisting := app.loadExistingConfig() == nil
	printStatus("1) Use existing instances; 2) Use saved configuration; 3) Configure new instances; 4) Maximum Free Tier")
	choice := 1
	if !app.Config.AutoUseExisting && !app.Config.NonInteractive {
		choice, _ = promptIntRange("Choose configuration (1-4)", "1", 1, 4)
	}
	switch choice {
	case 2:
		if !hasExisting { return fmt.Errorf("no valid saved configuration") }
	case 3:
		app.configureCustomInstances(amd, cpus, memory, storage)
	case 4:
		app.configureMaximumFreeTier(amd, cpus, memory, storage)
	default:
		app.configureFromExistingInstances()
	}
	return validateInstanceConfig(app.InstanceConfig)
}

func (app *App) configureCustomInstances(availableAMD, availableARMOCPUs, availableARMMemory, availableStorage int) {
	config := &InstanceConfig{AMDMicroBootVolumeSizeGB: 50}
	app.InstanceConfig = config
	maxAMD := lesser(availableAMD, availableStorage/50)
	if app.OCIConfig.UbuntuImageOCID == "" { maxAMD = 0 }
	if maxAMD > 0 && !app.Config.NonInteractive {
		config.AMDMicroInstanceCount, _ = promptIntRange(fmt.Sprintf("AMD instances (0-%d)", maxAMD), "0", 0, maxAMD)
	}
	for i := 0; i < config.AMDMicroInstanceCount; i++ {
		name := fmt.Sprintf("amd-instance-%d", i+1)
		if !app.Config.NonInteractive { name = promptWithDefault("AMD hostname", name) }
		config.AMDMicroHostnames = append(config.AMDMicroHostnames, name)
	}
	remainingStorage := availableStorage - config.AMDMicroInstanceCount*50
	maxARM := lesser(FreeTierMaxARMInstances, lesser(availableARMOCPUs, lesser(availableARMMemory, remainingStorage/FreeTierMinBootVolumeGB)))
	if app.OCIConfig.UbuntuARMFlexImageOCID == "" || maxARM <= 0 { return }
	config.ARMFlexInstanceCount = 1
	if !app.Config.NonInteractive {
		config.ARMFlexInstanceCount, _ = promptIntRange(fmt.Sprintf("ARM instances (0-%d)", maxARM), "1", 0, maxARM)
	}
	remainingOCPUs, remainingMemory := availableARMOCPUs, availableARMMemory
	for i := 0; i < config.ARMFlexInstanceCount; i++ {
		remainingInstances := config.ARMFlexInstanceCount-i-1
		name := fmt.Sprintf("arm-instance-%d", i+1)
		if !app.Config.NonInteractive { name = promptWithDefault("ARM hostname", name) }
		maxOCPUs := remainingOCPUs-remainingInstances
		ocpus := maxOCPUs
		if !app.Config.NonInteractive { ocpus, _ = promptIntRange(fmt.Sprintf("OCPUs (1-%d)", maxOCPUs), strconv.Itoa(maxOCPUs), 1, maxOCPUs) }
		maxMemory := lesser(ocpus*6, remainingMemory-remainingInstances)
		memory := maxMemory
		if !app.Config.NonInteractive { memory, _ = promptIntRange(fmt.Sprintf("Memory GB (1-%d)", maxMemory), strconv.Itoa(maxMemory), 1, maxMemory) }
		maxBoot := remainingStorage-remainingInstances*FreeTierMinBootVolumeGB
		boot := lesser(50, maxBoot)
		if !app.Config.NonInteractive { boot, _ = promptIntRange(fmt.Sprintf("Boot GB (%d-%d)", FreeTierMinBootVolumeGB, maxBoot), strconv.Itoa(boot), FreeTierMinBootVolumeGB, maxBoot) }
		config.ARMFlexHostnames = append(config.ARMFlexHostnames, name)
		config.ARMFlexOCPUsPerInstance = append(config.ARMFlexOCPUsPerInstance, ocpus)
		config.ARMFlexMemoryPerInstance = append(config.ARMFlexMemoryPerInstance, memory)
		config.ARMFlexBootVolumeSizeGB = append(config.ARMFlexBootVolumeSizeGB, boot)
		config.ARMFlexBlockVolumes = append(config.ARMFlexBlockVolumes, 0)
		remainingOCPUs -= ocpus
		remainingMemory -= memory
		remainingStorage -= boot
	}
}

func (app *App) configureMaximumFreeTier(availableAMD, availableARMOCPUs, availableARMMemory, availableStorage int) {
	config := &InstanceConfig{AMDMicroBootVolumeSizeGB: 50}
	app.InstanceConfig = config
	if app.OCIConfig.UbuntuImageOCID != "" { config.AMDMicroInstanceCount = lesser(availableAMD, availableStorage/50) }
	for i := 0; i < config.AMDMicroInstanceCount; i++ { config.AMDMicroHostnames = append(config.AMDMicroHostnames, fmt.Sprintf("amd-instance-%d", i+1)) }
	remainingStorage := availableStorage-config.AMDMicroInstanceCount*50
	if app.OCIConfig.UbuntuARMFlexImageOCID != "" && availableARMOCPUs > 0 && availableARMMemory > 0 && remainingStorage >= FreeTierMinBootVolumeGB {
		config.ARMFlexInstanceCount = 1
		config.ARMFlexOCPUsPerInstance = []int{availableARMOCPUs}
		config.ARMFlexMemoryPerInstance = []int{lesser(availableARMMemory, availableARMOCPUs*6)}
		config.ARMFlexBootVolumeSizeGB = []int{remainingStorage}
		config.ARMFlexHostnames = []string{"arm-instance-1"}
		config.ARMFlexBlockVolumes = []int{0}
	}
}

func validateInstanceConfig(config *InstanceConfig) error {
	if config.AMDMicroInstanceCount < 0 || config.AMDMicroInstanceCount > FreeTierMaxAMDInstances || config.ARMFlexInstanceCount < 0 || config.ARMFlexInstanceCount > FreeTierMaxARMInstances {
		return fmt.Errorf("instance count exceeds Free Tier limits")
	}
	if len(config.AMDMicroHostnames) != config.AMDMicroInstanceCount { return fmt.Errorf("AMD hostname count does not match instance count") }
	for _, values := range []int{len(config.ARMFlexHostnames), len(config.ARMFlexOCPUsPerInstance), len(config.ARMFlexMemoryPerInstance), len(config.ARMFlexBootVolumeSizeGB), len(config.ARMFlexBlockVolumes)} {
		if values != config.ARMFlexInstanceCount { return fmt.Errorf("ARM configuration array length does not match instance count") }
	}
	storage := config.AMDMicroInstanceCount*config.AMDMicroBootVolumeSizeGB
	if config.AMDMicroInstanceCount > 0 && config.AMDMicroBootVolumeSizeGB < FreeTierMinBootVolumeGB { return fmt.Errorf("AMD boot volume below minimum") }
	cpus, memory := 0, 0
	for i := 0; i < config.ARMFlexInstanceCount; i++ {
		if config.ARMFlexOCPUsPerInstance[i] < 1 || config.ARMFlexMemoryPerInstance[i] < 1 || config.ARMFlexBootVolumeSizeGB[i] < FreeTierMinBootVolumeGB || config.ARMFlexBlockVolumes[i] < 0 {
			return fmt.Errorf("invalid ARM allocation at index %d", i)
		}
		cpus += config.ARMFlexOCPUsPerInstance[i]
		memory += config.ARMFlexMemoryPerInstance[i]
		storage += config.ARMFlexBootVolumeSizeGB[i]+config.ARMFlexBlockVolumes[i]
	}
	if cpus > FreeTierMaxARMOCPUs || memory > FreeTierMaxARMMemoryGB || storage > FreeTierMaxStorageGB { return fmt.Errorf("configuration exceeds Free Tier CPU, memory, or storage limits") }
	return nil
}
