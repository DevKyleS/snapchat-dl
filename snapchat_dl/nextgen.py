from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

# https://github.com/Snapchat/storykit/blob/main/gqlschema/public_story_api.graphql


# Select your transport with a defined url endpoint
transport = AIOHTTPTransport(
    url="https://story.snapchat.com/api/proxy-to-backend/graphql"
)

# Create a GraphQL client using the defined transport
client = Client(transport=transport, fetch_schema_from_transport=True)

# Provide a GraphQL query
query = gql(
    #    """
    #    query PublishedPremiumStories($businessProfileId: "ccbfbac1-40c2-4348-9448-d37f36494380", $seasonId: "f0b19725-2c15-494c-be46-b7abfd77aeec", $cursor: "", $limit: 10, $country: "US")
    # """
    """
    query PublishedPremiumStories($businessProfileId: ID!, $seasonId: ID, $cursor: ID!, $limit: Int!, $country: String!) {
  publisher(businessProfileId: $businessProfileId) {
    businessProfileId
    publishedPremiumStoriesConnection(
      first: $limit
      from: $cursor
      seasonId: $seasonId
      country: $country
    ) {
      ...PublishedPremiumStories
      __typename
    }
    __typename
  }
}

fragment PublishedPremiumStories on PublishedPremiumStoriesConnection {
  premiumStories {
    ...PublishedPremiumStory
    __typename
  }
  pageInfo {
    nextCursor
    __typename
  }
  __typename
}

fragment PublishedPremiumStory on PremiumStory {
  story {
    ...PublishedStory
    __typename
  }
  publishedTimeInSec
  seasonNumber
  episodeNumber
  ownerBusinessProfileId
  __typename
}

fragment PublishedStory on Story {
  id
  title
  thumbnailUrl
  type
  videoTrackUrl
  __typename
}

    """
)


# Execute the query on the transport
result = client.execute(query)
print(result)
