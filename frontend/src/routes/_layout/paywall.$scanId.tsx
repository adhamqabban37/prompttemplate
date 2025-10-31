import {
  Badge,
  Box,
  Button,
  Container,
  Heading,
  HStack,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useParams } from "@tanstack/react-router";
import { CheckCircle2, Sparkles } from "lucide-react";

type BillingMe = {
  premium: boolean;
  plan: "free" | "premium";
  stripe_checkout_url?: string | null;
};

export const Route = createFileRoute("/_layout/paywall/$scanId" as any)({
  component: PaywallPage,
});

function PaywallPage() {
  const { scanId } = useParams({ from: "/_layout/paywall/$scanId" }) as {
    scanId: string;
  };

  const billingQuery = useQuery<BillingMe>({
    queryKey: ["billing", "me"],
    queryFn: async () => {
      const r = await fetch(`/api/v1/billing/me`);
      if (!r.ok) throw new Error("Failed to fetch billing info");
      return r.json();
    },
  });

  const handleUpgrade = () => {
    const url = billingQuery.data?.stripe_checkout_url;
    if (url) window.location.href = url;
  };

  if (billingQuery.isLoading) {
    return (
      <Container maxW="3xl" py={12}>
        <VStack gap={4}>
          <Spinner size="xl" color="purple.500" />
          <Text color="gray.400">Loading billing…</Text>
        </VStack>
      </Container>
    );
  }

  if (billingQuery.isError) {
    return (
      <Container maxW="3xl" py={12}>
        <VStack gap={3}>
          <Heading size="md" color="red.400">
            Failed to load billing
          </Heading>
          <Text color="gray.300">
            {billingQuery.error instanceof Error
              ? billingQuery.error.message
              : "Unknown error"}
          </Text>
        </VStack>
      </Container>
    );
  }

  const billing = billingQuery.data!;

  if (billing.premium) {
    return (
      <Box bg="gray.900" color="gray.100" minH="100vh" py={16}>
        <Container maxW="3xl" textAlign="center">
          <VStack gap={6}>
            <Badge colorScheme="purple" fontSize="md" px={3} py={1}>
              Scan #{scanId} Complete
            </Badge>
            <Heading size="xl">You already have Premium</Heading>
            <Text color="gray.300">View your full report now.</Text>
            <a href={`/premium/${scanId}`}>
              <Button colorScheme="purple">Go to Full Report</Button>
            </a>
          </VStack>
        </Container>
      </Box>
    );
  }

  return (
    <Box bg="gray.900" color="gray.100" minH="100vh" py={16}>
      <Container maxW="3xl" textAlign="center">
        <VStack gap={6}>
          <Sparkles size={40} />
          <Heading size="xl">Unlock Your Full Report</Heading>
          <Text color="gray.300">
            Upgrade to Premium to access complete analysis, insights, and
            recommendations for this scan.
          </Text>
          {billing.stripe_checkout_url ? (
            <Button size="lg" colorScheme="purple" onClick={handleUpgrade}>
              Upgrade to Premium
            </Button>
          ) : (
            <Text color="gray.400">
              Checkout not configured yet. Please contact support.
            </Text>
          )}
          <HStack color="gray.400" fontSize="sm" gap={4} justify="center">
            <HStack>
              <CheckCircle2 size={16} />
              <Text>Instant Access</Text>
            </HStack>
            <HStack>
              <CheckCircle2 size={16} />
              <Text>Cancel Anytime</Text>
            </HStack>
          </HStack>
        </VStack>
      </Container>
    </Box>
  );
}

export default PaywallPage;
