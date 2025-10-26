import { Box, Container, Heading, Input, Button, Stack } from "@chakra-ui/react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/_layout/")({
  component: Home,
});

function Home() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    navigate({ to: "/dashboard", search: { url } });
  };

  return (
    <Container maxW="lg" py={16}>
      <Stack spacing={6}>
        <Heading size="lg">Xenlixai</Heading>
        <Box as="form" onSubmit={onSubmit}>
          <Stack direction={{ base: "column", md: "row" }} spacing={3}>
            <Input
              placeholder="Enter your website URL (https://example.com)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <Button type="submit" colorScheme="blue">
              Analyze
            </Button>
          </Stack>
        </Box>
      </Stack>
    </Container>
  );
}
