#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/network-stack';
import { ChatwootStack } from '../lib/chatwoot-stack';
import { FeStack } from '../lib/fe-stack';
import { LambdaStack } from '../lib/lambda-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

const network = new NetworkStack(app, 'NetworkStack', { env });
new ChatwootStack(app, 'ChatwootStack', {
  env,
  vpc: network.vpc,
  keyPairName: app.node.tryGetContext('chatwoot:keyPairName'),
  sshPublicKey: app.node.tryGetContext('chatwoot:sshPublicKey'),
  allowedSshCidr: app.node.tryGetContext('chatwoot:allowedSshCidr'),
  allowedChatwootCidr: app.node.tryGetContext('chatwoot:allowedChatwootCidr'),
});
new FeStack(app, 'FeStack', { env });
new LambdaStack(app, 'LambdaStack', { env });
