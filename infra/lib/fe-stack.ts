import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as path from 'path';
import { Construct } from 'constructs';

export class FeStack extends cdk.Stack {
  public readonly websiteUrl: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const websiteBucket = new s3.Bucket(this, 'ChatwootFeBucket', {
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      publicReadAccess: true,
      blockPublicAccess: new s3.BlockPublicAccess({
        blockPublicAcls: false,
        blockPublicPolicy: false,
        ignorePublicAcls: false,
        restrictPublicBuckets: false,
      }),
    });

    new s3deploy.BucketDeployment(this, 'DeployFe', {
      sources: [
        s3deploy.Source.asset(path.join(__dirname, '../../chatwoot-fe'), {
          exclude: ['node_modules', '**/node_modules', 'package-lock.json'],
        }),
      ],
      destinationBucket: websiteBucket,
    });

    this.websiteUrl = websiteBucket.bucketWebsiteUrl;
    new cdk.CfnOutput(this, 'FeWebsiteUrl', {
      value: this.websiteUrl,
      description: 'Chatwoot FE static website URL (S3 website hosting)',
    });
  }
}
