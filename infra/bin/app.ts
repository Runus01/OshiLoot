import { App } from "aws-cdk-lib";
import { AppStack } from "../lib/app-stack.ts";
import { BaseStack } from "../lib/base-stack.ts";

const app = new App();

// Account and region come from your AWS CLI profile (or the GitHub Actions role).
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

// Deploy once from your laptop: the image registry and the role GitHub Actions uses.
new BaseStack(app, "OshiLootBase", { env, description: "OshiLoot: ECR repo and GitHub deploy role" });

// Deployed by GitHub Actions on every push to main.
new AppStack(app, "OshiLootApp", { env, description: "OshiLoot: Lambda, DynamoDB, S3, CloudFront" });
