# SSH to Chatwoot EC2

## If `ssh ubuntu@<ip>` gives "Permission denied (publickey)"

### Option A: EC2 Instance Connect (quick one-time access)

1. **Get instance ID and AZ:**
   ```bash
   INSTANCE_ID=$(aws ec2 describe-instances --filters "Name=ip-address,Values=44.215.200.55" --query "Reservations[0].Instances[0].InstanceId" --output text)
   AZ=$(aws ec2 describe-instances --filters "Name=ip-address,Values=44.215.200.55" --query "Reservations[0].Instances[0].Placement.AvailabilityZone" --output text)
   echo $INSTANCE_ID $AZ
   ```

2. **Push your key (valid 60 seconds) and SSH immediately:**
   ```bash
   aws ec2-instance-connect send-ssh-public-key \
     --instance-id $INSTANCE_ID \
     --instance-os-user ubuntu \
     --availability-zone $AZ \
     --ssh-public-key file://$HOME/.ssh/id_ed25519.pub

   ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no ubuntu@44.215.200.55
   ```

3. **Once logged in, add your key permanently** so you don’t need to push it again:
   ```bash
   # On your Mac, copy your public key to the clipboard (or print it):
   cat ~/.ssh/id_ed25519.pub

   # On the EC2 instance, paste that one line into the next command:
   echo "PASTE_YOUR_PUBLIC_KEY_LINE_HERE" >> /home/ubuntu/.ssh/authorized_keys
   ```
   Then exit and from your Mac run `ssh ubuntu@44.215.200.55` again; it should work without Instance Connect.

### Option B: AWS Console (browser)

1. Open **EC2** → **Instances** → select the instance with IP `44.215.200.55`.
2. Click **Connect** → **EC2 Instance Connect** → **Connect** (browser shell).
3. In that shell, add your Mac public key (get it on your Mac with `cat ~/.ssh/id_ed25519.pub` and paste):
   ```bash
   echo "ssh-ed25519 AAAA... your@email" >> /home/ubuntu/.ssh/authorized_keys
   ```
4. From your Mac: `ssh ubuntu@44.215.200.55`.
