#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { FrontDoorStack } from '../lib/front-door-stack';

const app = new cdk.App();

// us-east-1 on purpose: CloudFront only accepts ACM certificates from there,
// and keeping cert + CDN + Lambda in one stack avoids cross-region wiring.
// The Lambda calls the AgentCore Runtime in its own region via the SDK.
new FrontDoorStack(app, 'CvAgentFrontDoor', {
  env: { region: 'us-east-1' },
});
