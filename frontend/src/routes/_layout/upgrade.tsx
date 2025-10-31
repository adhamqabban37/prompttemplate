import { Container, Heading, Stack, Text } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/upgrade")({
  component: Upgrade,
})

function Upgrade() {
  return (
    <Container maxW="lg" py={8}>
      <Stack gap={4}>
        <Heading size="md">Upgrade</Heading>
        <Text>Stripe Checkout will be wired here.</Text>
      </Stack>
    </Container>
  )
}
