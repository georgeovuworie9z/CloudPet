# This bootstrap configuration deliberately uses LOCAL state
# (terraform/bootstrap/terraform.tfstate, git-ignored via terraform/.gitignore).
#
# It exists only to create the S3 bucket that stores the *remote* state for
# every real environment (environments/production, ...). That bucket cannot
# store its own creator's state (chicken-and-egg), so this configuration stays
# on local state permanently.
#
# The local state here contains only the state bucket's own attributes (name,
# ARN, versioning / encryption / policy config) and a random_id suffix. It
# holds no secrets and is never committed.

terraform {
  backend "local" {}
}
