import {
  Badge,
  Box,
  Container,
  Heading,
  HStack,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useParams } from "@tanstack/react-router";

// Minimal, Chakra v3-compatible implementation
interface FullScanResult {
  visibility_score?: number;
  geo_score?: number;
  aeo_score?: number;
  url?: string;
}

export const Route = createFileRoute("/_layout/premium/$scanId" as any)({
  component: PremiumDashboard,
});

function PremiumDashboard() {
  const { scanId } = useParams({ from: "/_layout/premium/$scanId" }) as {
    scanId: string;
  };

  const fullQuery = useQuery<FullScanResult>({
    queryKey: ["scan", "full", scanId],
    queryFn: async () => {
      const r = await fetch(`/api/v1/scan-jobs/${scanId}/full`);
      if (!r.ok) {
        if (r.status === 425) throw new Error("Scan not ready yet");
        throw new Error(`Failed to load full scan: ${r.status}`);
      }
      return r.json();
    },
    retry: 1,
  });

  if (fullQuery.isLoading) {
    return (
      <Container maxW="3xl" py={12}>
        <VStack gap={4}>
          <Spinner size="xl" color="purple.500" />
          <Text color="gray.400">Loading full report…</Text>
        </VStack>
      </Container>
    );
  }

  if (fullQuery.isError) {
    return (
      <Container maxW="3xl" py={12}>
        <VStack gap={4}>
          <Text color="red.400" fontWeight="semibold">
            {(fullQuery.error as Error)?.message || "Failed to load report"}
          </Text>
        </VStack>
      </Container>
    );
  }

  const data = fullQuery.data || {};

  return (
    <Box bg="gray.900" color="gray.100" minH="100vh" py={16}>
      <Container maxW="4xl">
        <VStack gap={6} align="stretch">
          <VStack gap={2} textAlign="center">
            <Badge colorScheme="purple" fontSize="md" px={3} py={1}>
              Scan #{scanId}
            </Badge>
            <Heading size="xl">Premium Report</Heading>
            <Text color="gray.300">Full analysis and recommendations</Text>
          </VStack>

          <Box bg="gray.800" p={6} borderRadius="md">
            <Heading size="md" mb={2}>
              Overview
            </Heading>
            <Text color="gray.300" fontFamily="mono" mb={2}>
              URL: {data.url || "(unknown)"}
            </Text>
            <HStack>
              <Text color="gray.300">
                Visibility: {data.visibility_score ?? "—"}
              </Text>
              <Text color="gray.300">GEO: {data.geo_score ?? "—"}</Text>
              <Text color="gray.300">AEO: {data.aeo_score ?? "—"}</Text>
            </HStack>
          </Box>
        </VStack>
      </Container>
    </Box>
  );
}

export default PremiumDashboard;
