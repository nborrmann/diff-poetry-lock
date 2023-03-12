# Diff poetry.lock

Poetry's lockfiles are very verbose and hard to make sense of. This makes it hard to keep track of what dependencies
changed in a pull request. This Github Action aims to solve this problem by posting a readable summary of all changes
to your pull requests.

## Example

<img width="916" alt="image" src="https://user-images.githubusercontent.com/1723176/224580589-bd5e7a5f-e39f-40d3-91a2-b4bd02284100.png">

## Usage

Simply add the following step to your Github Action:

```yaml
    steps:
      - name: Diff poetry.lock
        uses: nborrmann/diff-poetry-lock
```

When the diff changes during the lifetime of a pull request, the original comment will be updated (or deleted in case
all changes are rolled back).
