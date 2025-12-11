"""
GitHub GraphQL Queries.

Optimized queries for issue discovery with minimal data transfer.
"""

# Search issues with pagination
SEARCH_ISSUES_QUERY = """
query SearchIssues($query: String!, $first: Int!, $after: String) {
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
  search(query: $query, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        ... on Issue {
          id
          number
          title
          body
          url
          state
          createdAt
          updatedAt
          closedAt
          labels(first: 10) {
            nodes {
              name
            }
          }
          repository {
            nameWithOwner
            owner {
              login
            }
            name
            url
            stargazerCount
            forkCount
            primaryLanguage {
              name
            }
            repositoryTopics(first: 10) {
              nodes {
                topic {
                  name
                }
              }
            }
            pushedAt
          }
        }
      }
    }
  }
}
"""

# Get detailed issue information
GET_ISSUE_DETAILS_QUERY = """
query GetIssueDetails($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      id
      number
      title
      body
      url
      state
      stateReason
      createdAt
      updatedAt
      closedAt
      labels(first: 20) {
        nodes {
          name
        }
      }
      assignees(first: 5) {
        totalCount
      }
      comments(first: 1) {
        totalCount
      }
      timelineItems(first: 1, itemTypes: [REFERENCED_EVENT]) {
        totalCount
      }
    }
  }
  rateLimit {
    remaining
    resetAt
  }
}
"""

# Check issue status (lightweight)
CHECK_ISSUE_STATUS_QUERY = """
query CheckIssueStatus($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      state
      stateReason
      closedAt
    }
  }
}
"""

# Get repository metadata
GET_REPO_METADATA_QUERY = """
query GetRepoMetadata($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    stargazerCount
    forkCount
    pushedAt
    primaryLanguage {
      name
    }
    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
      edges {
        size
        node {
          name
        }
      }
    }
    repositoryTopics(first: 20) {
      nodes {
        topic {
          name
        }
      }
    }
    mentionableUsers {
      totalCount
    }
  }
  rateLimit {
    remaining
    resetAt
  }
}
"""
