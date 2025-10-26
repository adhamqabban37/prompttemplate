import { Container, Heading, Text, Stack } from "@chakra-ui/react";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_layout/success")({
  component: Success,
});

function Success() {
  return (
    <Container maxW="lg" py={8}>
      <Stack spacing={4}>
        <Heading size="md">Payment Success</Heading>
        <Text>Your upgrade was successful. Premium dashboard coming next.</Text>
      </Stack>
    </Container>
  );
}
