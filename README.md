# Amazon Price Drop Alert

This is an application that tracks price drops of selected products on Amazon and sends email alerts.

**⚠️ Important Note ⚠️**: 
* This is a personal project and is not intended for commercial use.
* An Amazon product webpage might be unscrappedable at any given moment for some reason. Perhaps due to repeated requests in a short period of time. It's possible that in one run you can get the price, and in the next run you get 404, and it doesn't necessarily mean there's something wrong with the code.

## Prerequisites
```
# AWS CLI
brew install awscli
# aws configure is crucial to local testing and deployment to AWS
aws configure
# for detailed configure instruction please reach out to author

# terraform
brew install terraform

# pyenv and virtualenv, if you don't have already
brew install pyenv pyenv-virtualenv

# set up python virtual env
pyenv install 3.12 # the app is written with this version but other version might be fine
pyenv virtualenv 3.12 amazon_price_checker # feel free to use a different name
pyenv local amazon_price_checker # Make the virtual environment auto-activate in this project directory
pyenv activate amazon_price_checker
# optional: to deactivate later
pyenv deactivate

# install dependencies
pip install -r requirements.txt

# set up pre-commit hooks, which includes linters
pre-commit install

```

## Running the Program Locally

To run the program locally, use the following command:
```sh
python -m app.amazon_price_checker
```

## AWS Lambda

In production, the program is powered by AWS Lambda. The Lambda handler is located in `src/aws_lambda_handler`.
After making local changes, the steps to deploy are:
```sh
git add .
git commit
pip freeze > requirements.txt # if new libraries are introduced
git push
```

## Continuous Integration & Deployment

Continuous Integration (CI) is performed by GitHub Actions. The configuration for GitHub Actions is in `deploy.yml`.


## Infrastructure Management

Terraform is used for infrastructure management. In `main.tf`, a cron job is set to run the program at 8am EDT every day.

To deploy a terraform change:
```
cd terraform
# requires aws cli to be properly setup
terraform init  # just need to run once after you setup aws cli
terraform validate # just need to run once after you setup aws cli
terraform plan # every time you make a change to a terraform file
terraform apply -auto-approve # every time you make a change to a terraform file
```

## Add an Amazon product to the price drop watchlist
in project root directory, run:
```sh
python -m app.s3_data_processor
```
