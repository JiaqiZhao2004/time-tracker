# Time Tracker

![Time Tracker Demo](demo.png)

A modern, cloud-native time tracking application built with a serverless architecture on AWS, featuring real-time data visualization and one-click category tracking.

## Architecture Overview

**Frontend**: Vue 3 + TypeScript + Vite, deployed to S3 + CloudFront via GitHub Actions  
**Backend**: AWS Lambda (Python 3.11+) + API Gateway  
**Database**: DynamoDB with single-table design  
**CI/CD**: GitHub Actions for automated frontend deployment

## Features

### Core Functionality
- **One-click time tracking** across nine life categories: coursework, work, prayer, rest, social, family, chores, self-study, exercise
- **Interactive timeline visualization** showing daily activity distribution
- **Local timezone support** with UTC-backed storage for data consistency
- **Real-time updates** with optimistic UI patterns

### Technical Highlights
- **Serverless architecture**: Zero server maintenance, automatic scaling, pay-per-use pricing
- **DynamoDB single-table design**: Optimized access patterns with composite keys for efficient queries
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
VITE_API_BASE=http://localhost:8000 npm run dev
```

### Backend & Infrastructure
- **AWS Lambda**: Serverless compute with Python runtime
- **FastAPI**: Local v2 API service for development against DynamoDB
- **API Gateway**: RESTful API endpoint management with CORS support
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
containing the Mangum-backed Lambda function, HTTP API routes, CORS settings,
and permissions for the existing `time-tracker-v2` DynamoDB table. Deploy it
from the repository root:

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
`time-tracker-v2`. The stack output `ApiBaseUrl` is the value to provide as
`VITE_API_BASE` when building the frontend.

The first guided deployment saves choices such as the stack name, AWS region,
and parameters to `samconfig.toml`. After that, rebuild and deploy with:

```bash
sam build --use-container
sam deploy
```

SAM asks whether `TimeTrackerBackendFunction` can remain unauthenticated once
for each public HTTP API route. This application currently relies on public
API endpoints, so accept those prompts only when that is intended.

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

- `GET /categories` accepts `user_id` and returns active and inactive category definitions.
- `POST /categories` accepts `user_id` and a validated category `name`.
- `PATCH /categories/{categoryId}` accepts `user_id` and `isActive` to disable or re-enable a category.
- `POST /entries` accepts `user_id`, `categoryId`, and a timezone-aware `timestamp`.
- `GET /entries-local` accepts `user_id`, `timezone`, `date`, and optional `period=day|week` query parameters; it returns the resolved `period`, and weekly ranges use the Monday-starting local week containing `date`.

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

- Multi-user authentication with Amazon Cognito
- Custom domain with AWS Route 53
