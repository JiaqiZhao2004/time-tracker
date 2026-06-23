# Trace: A Time Observability App

![Trace Demo](demo.png)

Trace helps people see the shape of their time: what they spent it on, when
patterns repeat, and where they have room to adjust. It is a modern,
cloud-native time tracking application built with a serverless architecture on
AWS, featuring real-time data visualization, one-click category tracking, and
Google sign-in through Amazon Cognito.

## Architecture Overview

- **Frontend**: Vue 3 + TypeScript + Vite, deployed to S3 + CloudFront via GitHub Actions
- **Backend**: AWS Lambda (Python 3.14) + API Gateway
- **Database**: DynamoDB with single-table design
- **Auth**: Amazon Cognito Hosted UI with Google federation and API Gateway JWT authorization
- **CI/CD**: GitHub Actions for independent frontend and backend deployment

## Features

### Core Functionality
- **One-click time tracking** across nine life categories: coursework, work, prayer, rest, social, family, chores, self-study, exercise
- **Interactive timeline visualization** showing daily activity distribution
- **Local timezone support** with UTC-backed storage for data consistency
- **Real-time updates** with optimistic UI patterns
- **Personal time history** stored per authenticated user

### Technical Highlights
- **Serverless architecture**: Zero server maintenance, automatic scaling, pay-per-use pricing
- **DynamoDB single-table design**: Optimized access patterns with composite keys for efficient queries
- **Cognito authentication**: Google Hosted UI sign-in, OAuth authorization-code flow, ID-token API authorization, Hosted UI logout, and optional email allowlisting
- **RESTful API**: Clean API design with proper HTTP semantics via API Gateway
- **Type-safe frontend**: Full TypeScript implementation with Vue 3 Composition API
- **Responsive UI**: Compatible with both Mobile and Desktop views

## Tech Stack

### Frontend
- **Vue 3** with TypeScript
- **Modular component architecture** for maintainability

Frontend source lives in `frontend/`.

```bash
cd frontend
VITE_API_BASE=http://localhost:8000 \
VITE_COGNITO_AUTHORITY=https://cognito-idp.us-east-2.amazonaws.com/<user-pool-id> \
VITE_COGNITO_CLIENT_ID=<user-pool-client-id> \
VITE_COGNITO_DOMAIN=https://<domain-prefix>.auth.us-east-2.amazoncognito.com \
npm run dev
```

### Backend & Infrastructure
- **AWS Lambda**: Serverless compute with Python runtime
- **FastAPI**: Local v2 API service for development against DynamoDB
- **API Gateway**: RESTful API endpoint management with CORS and JWT authorizer support
- **Amazon Cognito**: Hosted UI, Google federation, OAuth client, user pool domain, callback URLs, and logout URLs
- **DynamoDB**: NoSQL database with provisioned or on-demand capacity
- **IAM**: Fine-grained access control for Lambda execution roles

The local FastAPI backend uses the v2 DynamoDB table `time-tracker-v2` and
requires configured AWS credentials and an AWS region with access to that
table.

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn backend.main:app --reload
```

For AWS Lambda behind API Gateway, `template.yaml` defines an AWS SAM stack
containing the Mangum-backed Lambda function, HTTP API routes, Cognito Hosted
UI with Google sign-in, API Gateway JWT authorization, CORS settings, and
permissions for the existing `time-tracker-v2` DynamoDB table. Deploy it from
the repository root:

```bash
sam validate --lint
sam build --use-container
sam deploy --guided
```

Run Docker before `sam build --use-container`; the container build ensures
Python binary dependencies are packaged for the Lambda runtime. The SAM stack
uses the DynamoDB table named by `TimeTrackerTableName` and does not create or
delete that table.

On the guided deployment, set `AllowedOrigins` to the deployed frontend origin
in addition to any local origins you still need, for example
`https://example.cloudfront.net,http://localhost:5173`. Set
`TimeTrackerTableName` if deploying against a table other than
`time-tracker-v2`.

For Google sign-in, first create a Google OAuth web client. After the first SAM
deploy, add the stack output `GoogleOAuthRedirectUri` as an authorized redirect
URI in that Google client, then deploy again if Cognito could not validate the
provider on the first pass. Set these SAM parameters:

- `GoogleOAuthClientId` and `GoogleOAuthClientSecret` from Google Cloud.
- `AllowedUserEmails` to a comma-separated allowlist such as
  `roy@example.com,friend@example.com`, or leave it empty to allow any
  authenticated Google user.
- `CognitoDomainPrefix` to a globally unique Hosted UI domain prefix.
- `AuthCallbackUrls` and `AuthLogoutUrls` to the frontend origins, for example
  `https://example.cloudfront.net,http://localhost:5173`.

The Cognito resources in `template.yaml` include:

- A user pool that uses email as the username and verifies email addresses.
- A Google identity provider with `openid`, `email`, and `profile` scopes.
- A public SPA user pool client using the OAuth authorization-code flow.
- A Cognito Hosted UI domain for sign-in and logout redirects.
- An API Gateway HTTP API JWT authorizer that validates Cognito ID tokens.
- Optional backend email allowlisting through `ALLOWED_USER_EMAILS`.

The stack output `ApiBaseUrl` is the value to provide as `VITE_API_BASE` when
building the frontend. Also set `VITE_COGNITO_AUTHORITY` from
`CognitoAuthority`, `VITE_COGNITO_CLIENT_ID` from `CognitoUserPoolClientId`,
and `VITE_COGNITO_DOMAIN` from `CognitoHostedUiDomain`.

The first guided deployment saves choices such as the stack name, AWS region,
and parameters to `samconfig.toml`. After that, rebuild and deploy with:

```bash
sam build --use-container
sam deploy
```

SAM may ask whether `TimeTrackerBackendFunction` can remain unauthenticated once
for each HTTP API route. The HTTP API is protected by the default Cognito JWT
authorizer in `template.yaml`; accept the prompts when SAM is referring to the
Lambda event permission model, not a deliberate unauthenticated app surface.

#### Automated Backend Deployment

Pushes to `main` that change `backend/**`, `template.yaml`, or
`samconfig.toml` run `.github/workflows/deploy-backend.yml`. The workflow runs
the backend test suite, validates and container-builds the SAM application,
then runs an unattended `sam deploy` against the existing
`time-tracker-sam-app` stack. Frontend-only pushes continue through the
separate S3 and CloudFront workflow.

The backend workflow assumes the dedicated OIDC role
`arn:aws:iam::975050092888:role/GitHubActionsSamDeploy`. Configure that IAM
role outside this stack with trust restricted to the `main` branch of
`JiaqiZhao2004/time-tracker`, and grant the CloudFormation, Lambda, API
Gateway, IAM, and SAM artifact-bucket permissions required to update this SAM
application. The existing `GitHubActionsS3Deploy` role remains scoped to the
frontend deployment. Configure the repository secrets
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and
`ALLOWED_USER_EMAILS` for unattended backend deploys. Configure repository
variables `VITE_COGNITO_AUTHORITY` and `VITE_COGNITO_CLIENT_ID` for frontend
deploys, plus `VITE_COGNITO_DOMAIN` for Cognito logout.

#### Troubleshooting SAM Uploads

If deployment fails with `S3 Bucket does not exist` while uploading
`TimeTrackerBackendFunction`, SAM's managed artifact bucket may have been
deleted while its bootstrap CloudFormation stack remains. Recreate that
managed bucket by deleting only the SAM bootstrap stack, then deploying again:

```bash
aws cloudformation delete-stack \
  --stack-name aws-sam-cli-managed-default \
  --region us-east-2
aws cloudformation wait stack-delete-complete \
  --stack-name aws-sam-cli-managed-default \
  --region us-east-2
sam deploy
```

This does not delete the `time-tracker-v2` DynamoDB table or the application
stack `time-tracker-sam-app`.

If packaging the Lambda without SAM, configure its handler as
`backend.main.handler`, or `main.handler` when the contents of `backend/` are
at the deployment root.

Its v2 endpoints require user-scoped category IDs:

- `GET /me` fetches or creates the authenticated user's profile.
- `PATCH /me` accepts `displayName` and updates the authenticated user's profile.
- `GET /categories` returns active and inactive category definitions.
- `POST /categories` accepts a validated category `name`, including emoji labels.
- `PATCH /categories/{categoryId}` accepts one or both of `name` and `isActive` to rename, disable, or re-enable a category.
- `POST /entries` accepts `categoryId` and a timezone-aware `timestamp`.
- `GET /entries-local` accepts `timezone`, `date`, and optional `period=day|week` query parameters; it returns the resolved `period`, and weekly ranges use the Monday-starting local week containing `date`.

All deployed endpoints require `Authorization: Bearer <Cognito ID token>`. The
frontend obtains that token through the Cognito Hosted UI Google sign-in flow and
adds it to API requests automatically. For local backend development only, set
`DEV_AUTH_USER_ID`, `DEV_AUTH_EMAIL`, and optionally `DEV_AUTH_DISPLAY_NAME` to
bypass API Gateway JWT claims while running Uvicorn.

To migrate the existing single-user `USER#roy` data after signing in once with
Google and finding the Cognito `sub`, run a dry run first:

```bash
python migration/migrate_user_partition.py \
  --from-user roy \
  --to-user <cognito-sub> \
  --email roy@example.com \
  --display-name Roy \
  --dry-run
```

Then run the same command without `--dry-run`. The script copies data items to
`USER#<cognito-sub>`, writes the DynamoDB profile item, and leaves `USER#roy`
in place for rollback.

To run backend tests:

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/pytest backend/tests
```

### Deployment & Hosting
- **S3**: Static website hosting for production frontend builds
- **CloudFront**: Global CDN for low-latency content delivery with edge caching
- **GitHub Actions**: Automated CI/CD pipeline for build, test, and deployment

## Future Enhancements

- Custom domain with AWS Route 53
