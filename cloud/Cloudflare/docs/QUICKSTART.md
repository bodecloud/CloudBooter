# Cloudflare Quick Start

## 1. Create an API token

1. Open [Create API token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/).
2. Grant at least: Account Workers Scripts Edit, Workers KV Storage Edit, Account R2 Edit, Account D1 Edit.
3. Copy the token (shown once).

## 2. Find your Account ID

Dashboard → Workers & Pages → Overview → Account ID (right sidebar), or any account URL.

## 3. Run CloudBooter

```bash
cd cloud/Cloudflare
export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ACCOUNT_ID="..."
NON_INTERACTIVE=true AUTO_DEPLOY=false ./setup_cloudflare_terraform.sh
```

Or via Python:

```bash
pip install -r requirements.txt
pip install -e .
python -m cloudbooter deploy \
  --account-id "$CLOUDFLARE_ACCOUNT_ID" \
  --api-token "$CLOUDFLARE_API_TOKEN" \
  --output-dir ./out \
  --non-interactive --no-auto-deploy
```

## 4. Inspect and apply

```bash
cd out   # or current dir if using the shell script
terraform init
terraform plan
terraform apply   # when ready
```

## 5. Call your Worker

After apply, open `https://<worker-name>.<your-subdomain>.workers.dev` (subdomain is account-specific; see [workers.dev](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)).

## Cleanup

```bash
terraform destroy
```
