import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface ChatwootStackProps extends cdk.StackProps {
  readonly vpc: ec2.IVpc;
  /** EC2 key pair name for SSH access. Omit if using sshPublicKey (e.g. from Mac). */
  readonly keyPairName?: string;
  /** Your Mac (or local) SSH public key so you can `ssh ubuntu@<ip>` without an EC2 key pair. e.g. contents of ~/.ssh/id_ed25519.pub */
  readonly sshPublicKey?: string;
  /** CIDR allowed for SSH (port 22). Default 0.0.0.0/0. Use a narrow range for production. */
  readonly allowedSshCidr?: string;
  /** CIDR allowed for Chatwoot UI (port 3000). Default 0.0.0.0/0. Use a narrow range for production. */
  readonly allowedChatwootCidr?: string;
}

export class ChatwootStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ChatwootStackProps) {
    super(scope, id, props);

    const {
      vpc,
      keyPairName: keyPairNameProp,
      sshPublicKey: sshPublicKeyProp,
      allowedSshCidr = '0.0.0.0/0',
      allowedChatwootCidr = '0.0.0.0/0',
    } = props;
    const keyPairName =
      keyPairNameProp ?? this.node.tryGetContext('chatwoot:keyPairName');
    const sshPublicKey =
      sshPublicKeyProp ?? this.node.tryGetContext('chatwoot:sshPublicKey');

    const useMacKey = typeof sshPublicKey === 'string' && sshPublicKey.length > 0;
    const keyPair = keyPairName
      ? ec2.KeyPair.fromKeyPairName(this, 'Key', keyPairName)
      : new ec2.KeyPair(this, 'ChatwootKeyPair', {
          keyPairName: `chatwoot-${this.stackName.toLowerCase()}-key`,
          type: ec2.KeyPairType.RSA,
          format: ec2.KeyPairFormat.PEM,
        });

    // Chatwoot AWS Marketplace AMI – name pattern from describe-images (product ID 28eb226c-174b-42ef-acdf-ca0f82854ec8)
    // e.g. chatwoot-v2026-01-29T10-35-55.279Z-28eb226c-174b-42ef-acdf-ca0f82854ec8
    const chatwootAmi = ec2.MachineImage.lookup({
      name: 'chatwoot-v*28eb226c-174b-42ef-acdf-ca0f82854ec8',
      owners: ['aws-marketplace'],
    });

    const sg = new ec2.SecurityGroup(this, 'ChatwootSg', {
      vpc,
      description: 'Allow SSH and Chatwoot UI',
      allowAllOutbound: true,
    });
    sg.addIngressRule(
      ec2.Peer.ipv4(allowedSshCidr),
      ec2.Port.tcp(22),
      'SSH'
    );
    sg.addIngressRule(
      ec2.Peer.ipv4(allowedChatwootCidr),
      ec2.Port.tcp(3000),
      'Chatwoot UI'
    );

    const userData = ec2.UserData.forLinux();
    if (useMacKey && sshPublicKey) {
      const keyLine = sshPublicKey.trim().replace(/\r?\n/g, '');
      const keyB64 = Buffer.from(keyLine, 'utf8').toString('base64');
      userData.addCommands(
        'mkdir -p /home/ubuntu/.ssh',
        'chown ubuntu:ubuntu /home/ubuntu/.ssh',
        'chmod 700 /home/ubuntu/.ssh',
        `echo "${keyB64}" | base64 -d >> /home/ubuntu/.ssh/authorized_keys`,
        'chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys',
        'chmod 600 /home/ubuntu/.ssh/authorized_keys'
      );
    }

    const instance = new ec2.Instance(this, 'ChatwootInstance', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MEDIUM
      ), // 2 vCPU, 4 GiB
      machineImage: chatwootAmi,
      securityGroup: sg,
      keyPair,
      userData,
    });

    const eip = new ec2.CfnEIP(this, 'ChatwootEip', {
      domain: 'vpc',
      instanceId: instance.instanceId,
    });

    new cdk.CfnOutput(this, 'ChatwootUrl', {
      value: `http://${eip.attrPublicIp}:3000`,
      description: 'Chatwoot UI URL',
    });
    new cdk.CfnOutput(this, 'ChatwootPublicIp', {
      value: eip.attrPublicIp,
      description: 'Chatwoot instance public IP',
    });

    if (!keyPairName && 'privateKey' in keyPair) {
      const param = (keyPair as ec2.KeyPair).privateKey;
      new cdk.CfnOutput(this, 'ChatwootPrivateKeyParam', {
        value: param.parameterName,
        description:
          'SSM parameter with the EC2 private key. Retrieve with: aws ssm get-parameter --name <value> --with-decryption --query Parameter.Value --output text',
      });
    }

    if (useMacKey) {
      new cdk.CfnOutput(this, 'ChatwootSshCommand', {
        value: `ssh ubuntu@${eip.attrPublicIp}`,
        description: 'SSH from your Mac (use the key that matches the public key you provided)',
      });
    }
  }
}
