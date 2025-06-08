#!/bin/bash
set -e

YAML_FILE="lib/info.yaml"
COMMIT_MSG="$(git log -1 --pretty=%s)"
DATE=$(date +'%Y-%m-%d')

if [ ! -f "$YAML_FILE" ]; then
    echo "YAML file not found: $YAML_FILE"
    exit 0
fi

# [info] auto-commit check
if [ "$COMMIT_MSG" == "[info]" ]; then
    exit 0
fi

ESCAPED_COMMIT_MSG=$(printf '%s' "$COMMIT_MSG" | sed 's/"/\\"/g')

# Update latest-commit-msg
if grep -q "^latest-commit-msg:" "$YAML_FILE"; then
    sed -i "s/^latest-commit-msg:.*/latest-commit-msg: \"$ESCAPED_COMMIT_MSG\"/" "$YAML_FILE"
else
    echo "latest-commit-msg: \"$ESCAPED_COMMIT_MSG\"" >> "$YAML_FILE"
fi

# [no v] — only update latest-commit-date
if echo "$COMMIT_MSG" | grep -q '\[no v\]'; then
    sed -i "s/^latest-commit-date:.*/latest-commit-date: ${DATE}/" "$YAML_FILE"
    exit 0
fi

CURRENT_VERSION=$(grep '^version:' "$YAML_FILE" | awk '{print $2}')
IFS='.' read -r OLD_MAJOR OLD_MINOR OLD_PATCH <<< "$CURRENT_VERSION"

NEW_MAJOR="$OLD_MAJOR"
NEW_MINOR="$OLD_MINOR"
NEW_PATCH="$OLD_PATCH"
NEW_VERSION=""
USED_OVERRIDE=0

# Process [vX.Y.Z] version override
VERSION_OVERRIDE=$(echo "$COMMIT_MSG" | grep -o '\[v[0-9]\+\.[0-9]\+\.[0-9]\+\]' | tr -d '[]v')

if [ -n "$VERSION_OVERRIDE" ]; then
    USED_OVERRIDE=1
    if ! echo "$VERSION_OVERRIDE" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        echo "Error: Invalid version string: [v$VERSION_OVERRIDE]"
        exit 1
    fi

    IFS='.' read -r NEW_MAJOR NEW_MINOR NEW_PATCH <<< "$VERSION_OVERRIDE"

    # Reject same version unless [allow same version]
    if [ "$NEW_MAJOR" -eq "$OLD_MAJOR" ] && [ "$NEW_MINOR" -eq "$OLD_MINOR" ] && [ "$NEW_PATCH" -eq "$OLD_PATCH" ]; then
        if echo "$COMMIT_MSG" | grep -q '\[allow same version\]'; then
            echo "Warning: Same version used again [$VERSION_OVERRIDE] (allowed by tag)."
        else
            echo "Error: Version $VERSION_OVERRIDE is already current. Use [allow same version] to bypass."
            exit 1
        fi
    fi

    # Reject downgrades
    if [ "$NEW_MAJOR" -lt "$OLD_MAJOR" ] || \
       { [ "$NEW_MAJOR" -eq "$OLD_MAJOR" ] && [ "$NEW_MINOR" -lt "$OLD_MINOR" ]; } || \
       { [ "$NEW_MAJOR" -eq "$OLD_MAJOR" ] && [ "$NEW_MINOR" -eq "$OLD_MINOR" ] && [ "$NEW_PATCH" -lt "$OLD_PATCH" ]; }
    then
        echo "Error: Version downgrade is not allowed."
        echo "Old: $CURRENT_VERSION, New: $VERSION_OVERRIDE"
        exit 1
    fi

    # Warn on large jumps
    MAJOR_DIFF=$((NEW_MAJOR - OLD_MAJOR))
    MINOR_DIFF=$((NEW_MINOR - OLD_MINOR))
    PATCH_DIFF=$((NEW_PATCH - OLD_PATCH))

    if [ "$MAJOR_DIFF" -gt 1 ] || [ "$MINOR_DIFF" -gt 1 ] || [ "$PATCH_DIFF" -gt 1 ]; then
        echo "Warning: Version increase greater than 1:"
        [ "$MAJOR_DIFF" -gt 1 ] && echo "  Major: $OLD_MAJOR → $NEW_MAJOR"
        [ "$MINOR_DIFF" -gt 1 ] && echo "  Minor: $OLD_MINOR → $NEW_MINOR"
        [ "$PATCH_DIFF" -gt 1 ] && echo "  Patch: $OLD_PATCH → $NEW_PATCH"
    fi

    NEW_VERSION="$NEW_MAJOR.$NEW_MINOR.$NEW_PATCH"

else
    # Auto semantic bump if tagged
    BUMP_TAG_COUNT=$(echo "$COMMIT_MSG" | grep -o '\[\(major\|minor\|patch\|bump\)\]' | wc -l)

    if [ "$BUMP_TAG_COUNT" -gt 1 ]; then
        echo "Warning: Multiple bump tags found. Using highest priority (major > minor > patch > bump)."
    fi

    if echo "$COMMIT_MSG" | grep -qE '\[major\]|\[bump-major\]'; then
        NEW_MAJOR=$((OLD_MAJOR+1)); NEW_MINOR=0; NEW_PATCH=0
    elif echo "$COMMIT_MSG" | grep -qE '\[minor\]|\[bump-minor\]'; then
        NEW_MINOR=$((OLD_MINOR+1)); NEW_PATCH=0
    elif echo "$COMMIT_MSG" | grep -qE '\[patch\]|\[bump-patch\]|\[bump\]'; then
        NEW_PATCH=$((OLD_PATCH+1))
    else
        sed -i "s/^latest-commit-date:.*/latest-commit-date: ${DATE}/" "$YAML_FILE"
        exit 0
    fi
    NEW_VERSION="$NEW_MAJOR.$NEW_MINOR.$NEW_PATCH"
fi

# Apply version update
sed -i "s/^version:.*/version: $NEW_VERSION/" "$YAML_FILE"

# Update release dates as needed
if [ "$NEW_MAJOR" != "$OLD_MAJOR" ]; then
    sed -i "s/^releasedate-major:.*/releasedate-major: $DATE/" "$YAML_FILE"
fi
if [ "$NEW_MINOR" != "$OLD_MINOR" ]; then
    sed -i "s/^releasedate-minor:.*/releasedate-minor: $DATE/" "$YAML_FILE"
fi
if [ "$NEW_PATCH" != "$OLD_PATCH" ]; then
    sed -i "s/^releasedate-patch:.*/releasedate-patch: $DATE/" "$YAML_FILE"
fi

# Always update latest-commit-date
sed -i "s/^latest-commit-date:.*/latest-commit-date: ${DATE}/" "$YAML_FILE"

# Stage and commit if changed
git config --global user.name "github-actions[bot]"
git config --global user.email "github-actions[bot]@users.noreply.github.com"
git add "$YAML_FILE"
if ! git diff --cached --quiet; then
    git commit -m "[info] Update info.yaml version to $NEW_VERSION"
    git push
fi

# Tagging
TAG="v${NEW_VERSION}"
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
    git tag "$TAG"
    git push origin "$TAG"
else
    echo "Tag $TAG already exists."
fi

echo "NEW_VERSION=$NEW_VERSION" >> "$GITHUB_ENV"