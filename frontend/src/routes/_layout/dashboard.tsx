import { Box, Container, Heading, Text, Stack, Code } from "@chakra-ui/react";
import { createFileRoute, useSearch } from "@tanstack/react-router";

export const Route = createFileRoute("/_layout/dashboard")({
  component: Dashboard,
});

function Dashboard() {
  const search = useSearch({ from: "/_layout/dashboard" });
  const url = (search as any)?.url as string | undefined;

  return (
    <Container maxW="4xl" py={8}>
      <Stack spacing={4}>
        <Heading size="md">Dashboard (preview)</Heading>
        {url ? (
          <Text>
            Placeholder summary for URL: <Code>{url}</Code>
          </Text>
        ) : (
          <Text>No URL provided. Go back and enter a website.</Text>
        )}
        <Box borderWidth="1px" borderRadius="md" p={4}>
          <Text>Content will appear here after we implement crawling and analysis.</Text>
        </Box>
      </Stack>
    </Container>
  );
}
