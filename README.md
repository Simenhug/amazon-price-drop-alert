# Amazon Price Drop Alert

This project tracks price drops on Amazon and sends alerts.

## Running the Program Locally

To run the program locally, use the following command:
```sh
python -m app.amazon_price_checker
```

## AWS Lambda

In production, the program is powered by AWS Lambda. The Lambda handler is located in `src/aws_lambda_handler`.

## Continuous Integration & Deployment

Continuous Integration (CI) is performed by GitHub Actions. The configuration for GitHub Actions is in `deploy.yml`.

## Infrastructure Management

Terraform is used for infrastructure management. In `main.tf`, a cron job is set to run the program at 8am EDT every day.