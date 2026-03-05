# Chatwoot on AWS (Marketplace AMI) – CDK

Repeatable CDK deployment for Chatwoot using the subscribed Marketplace AMI. Requires an active Chatwoot Marketplace subscription in the account/region.

## Deploy

From this directory:

```bash
npm run build
npx cdk deploy --all --require-approval never
```

After deploy, open the **ChatwootUrl** stack output (e.g. `http://<public-ip>:3000`) to access the Chatwoot UI.

## Optional

- **SSH from your Mac:** Use your Mac SSH key so you can `ssh ubuntu@<ip>`:
  ```bash
  npx cdk deploy --all --require-approval never -c chatwoot:sshPublicKey="$(cat ~/.ssh/id_ed25519.pub)"
  ```
  (Use `id_rsa.pub` if you use RSA.) A fallback EC2 key is always created; if Mac key login fails, see **ChatwootPrivateKeyParam** or [docs/SSH-CONNECT.md](docs/SSH-CONNECT.md).
- **EC2 key pair instead:** Create a key pair in the EC2 console, then:
  `npx cdk deploy --all --require-approval never -c chatwoot:keyPairName=your-key-name`
- **Restrict access (production):** Pass CIDRs for SSH and Chatwoot UI:
  `-c chatwoot:allowedSshCidr=1.2.3.4/32 -c chatwoot:allowedChatwootCidr=0.0.0.0/0`

## Commands

- `npm run build` – compile TypeScript
- `npx cdk deploy --all` – deploy NetworkStack and ChatwootStack
- `npx cdk diff` – compare with deployed stacks
- `npx cdk synth` – synthesize CloudFormation templates
