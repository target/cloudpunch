# Contributing to CloudPunch

These rules must be followed for any contributions to be merged into master. A Git installation is required. See [here](./docs/getting_started_git.md) for more information.

#### 1. Create Branch

```
git checkout -b <branch-name>
```

The branch name should a very concise summary of what the contribution entails.

#### 2. Make Changes

Make the desired changes to the code.

#### 3. Test Changes

##### Linter

It is recommended to use pep8 as the linter. Pep8 can be installed using pip:

```
pip install pep8
```

The maximum line length allowed is 125. Create the configuration required to change this:

```
mkdir ~/.config
vi ~/.config/pep8
```

Save the file as the following:

```
[pep8]
max-line-length = 125
```

Go into the CloudPunch main directory and run pep8:

```
pep8 .
```

All rules must pass

#### 4. Update Documentation

Any documentation that is effected by the requested changes must be updated. Make sure to check for any spelling or grammatical errors.

Documentation that should always be updated:
- Bump version in `cloudpunch/version`
- CHANGELOG.md

#### 5. Create Pull Request

When the desired and required changes are met, commit your code with a summary of the changes:

```
git commit -m "Summary of changes"
```

Push the commit to the project repo:

```
git push origin <branch-name>
```

Members of the CloudPunch team will review the code
