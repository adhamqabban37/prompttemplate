import { Button, Container, Heading, Stack, Text } from "@chakra-ui/react"
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/success")({
  component: Success,
})

function Success() {
  const search = useSearch({ from: "/_layout/success" }) as { scanId?: string }
  const navigate = useNavigate()

  const go = () => {
    const sid = search?.scanId
    if (sid) {
      navigate({ to: `/_layout/dashboard/full/${sid}` })
    } else {
      navigate({ to: "/dashboard" })
    }
  }

  return (
    <Container maxW="lg" py={8}>
      <Stack gap={4}>
        <Heading size="md">Payment Success</Heading>
        <Text>Your upgrade was successful. You now have premium access.</Text>
        <Button onClick={go} colorScheme="purple" alignSelf="start">
          Go to Premium Dashboard
        </Button>
      </Stack>
    </Container>
  )
}
