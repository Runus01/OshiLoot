import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from "aws-cdk-lib";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import type { Construct } from "constructs";
import { BACKEND_REPOSITORY, GITHUB_DEPLOY_ROLE, GITHUB_DEPLOY_USER } from "./names.ts";

const GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com";

/**
 * How GitHub Actions signs in to AWS.
 *
 * - "oidc" (default): GitHub hands AWS a short-lived token for each run, so no keys are
 *   stored anywhere. Needs an IAM identity provider for GitHub.
 * - "keys": an access key, stored as a GitHub secret, for a user that can do nothing but
 *   assume the deploy role. For accounts that can't add identity providers, such as
 *   accounts made with AWS's new sign-up (projects in AWS Settings), whose fixed policies
 *   deny iam:*Provider*.
 */
type GithubAuth = "oidc" | "keys";

export class BaseStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const githubAuth = String(this.node.tryGetContext("githubAuth") ?? "oidc") as GithubAuth;
    if (githubAuth !== "oidc" && githubAuth !== "keys") {
      throw new Error(`githubAuth must be "oidc" or "keys", not "${githubAuth}".`);
    }

    // Each push stores one image; keep only the last five so storage stays at a few cents.
    const repository = new ecr.Repository(this, "BackendRepository", {
      repositoryName: BACKEND_REPOSITORY,
      imageScanOnPush: true,
      lifecycleRules: [{ maxImageCount: 5 }],
      removalPolicy: RemovalPolicy.DESTROY,
      emptyOnDelete: true,
    });

    const deployRole = new iam.Role(this, "GithubDeployRole", {
      roleName: GITHUB_DEPLOY_ROLE,
      maxSessionDuration: Duration.hours(1),
      assumedBy: githubAuth === "oidc" ? this.githubOidcPrincipal() : this.deployUserPrincipal(),
    });

    repository.grantPullPush(deployRole);

    // Lets the deploy workflow sign in to ECR Public, so pulling the Lambda adapter image
    // gets the authenticated rate limit instead of the anonymous one.
    // The token only reads public images; it grants nothing in this account.
    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["ecr-public:GetAuthorizationToken", "sts:GetServiceBearerToken"],
        resources: ["*"],
      }),
    );

    // `cdk deploy` works by assuming the roles `cdk bootstrap` created.
    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["sts:AssumeRole"],
        resources: [`arn:aws:iam::${this.account}:role/cdk-*`],
      }),
    );

    new CfnOutput(this, "DeployRoleArn", {
      value: deployRole.roleArn,
      description: "Save as the AWS_DEPLOY_ROLE_ARN repository variable on GitHub",
    });
    new CfnOutput(this, "RepositoryUri", { value: repository.repositoryUri });
  }

  /** Only workflows running on this repo's main branch can assume the role. */
  private githubOidcPrincipal(): iam.IPrincipal {
    const githubRepo: string = this.node.getContext("githubRepo");
    if (!/^[\w.-]+\/[\w.-]+$/.test(githubRepo) || githubRepo.startsWith("YOUR_GITHUB_USERNAME")) {
      throw new Error(
        'Set "githubRepo" in infra/cdk.json to "<your-github-username>/oshiloot" ' +
          "(or pass -c githubRepo=...) before deploying OshiLootBase.",
      );
    }

    // An AWS account can hold only one provider for this URL. If you already have one,
    // deploy with -c createGithubOidcProvider=false to reuse it.
    const createProvider = this.node.tryGetContext("createGithubOidcProvider") !== false
      && this.node.tryGetContext("createGithubOidcProvider") !== "false";
    const provider = createProvider
      ? new iam.OidcProviderNative(this, "GithubOidc", {
          url: GITHUB_OIDC_URL,
          clientIds: ["sts.amazonaws.com"],
        })
      : iam.OidcProviderNative.fromOidcProviderArn(
          this,
          "GithubOidc",
          `arn:aws:iam::${this.account}:oidc-provider/token.actions.githubusercontent.com`,
        );

    return new iam.WebIdentityPrincipal(provider.oidcProviderArn, {
      StringEquals: { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      StringLike: { "token.actions.githubusercontent.com:sub": `repo:${githubRepo}:ref:refs/heads/main` },
    });
  }

  /**
   * A user with no console access and no permissions of its own: its access key can only
   * swap itself for an hour-long deploy role session. Create the key afterwards with
   * `aws iam create-access-key`, so the secret never passes through CloudFormation.
   */
  private deployUserPrincipal(): iam.IPrincipal {
    const user = new iam.User(this, "GithubDeployUser", { userName: GITHUB_DEPLOY_USER });
    user.addToPolicy(
      new iam.PolicyStatement({
        // configure-aws-credentials tags each session with the workflow and commit,
        // which shows up in CloudTrail next to whatever the deploy did.
        actions: ["sts:AssumeRole", "sts:TagSession"],
        resources: [`arn:aws:iam::${this.account}:role/${GITHUB_DEPLOY_ROLE}`],
      }),
    );
    new CfnOutput(this, "DeployUserName", {
      value: user.userName,
      description: "Create its access key with: aws iam create-access-key --user-name <this>",
    });
    return new iam.SessionTagsPrincipal(user);
  }
}
