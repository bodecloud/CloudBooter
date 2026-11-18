from setuptools import setup

setup(
    name="oci-terraform-setup",
    version="1.0.0",
    py_modules=["setup_oci_terraform"],
    install_requires=[
        "oci>=2.155.0",
        "python-terraform>=1.0.0",
        "cryptography>=3.2.1",
        "click>=8.0.0",
        "rich>=13.0.0",
        "pyyaml>=5.4",
        "jinja2>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "oci-terraform-setup=setup_oci_terraform:main",
        ],
    },
    python_requires=">=3.8",
) 