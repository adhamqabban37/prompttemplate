import {
  Box,
  Container,
  Heading,
  Text,
  Stack,
  Code,
  Spinner,
  VStack,
  Badge,
  HStack,
} from "@chakra-ui/react";
import { createFileRoute, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";

export const Route = createFileRoute("/_layout/dashboard")({
  component: Dashboard,
});

interface MetadataSummary {
  json_ld_count: number;
  microdata_count: number;
  opengraph_count: number;
}

interface Schema {
  type: string;
  data: any;
}

interface ScanResponse {
  url: string;
  title: string | null;
  description: string | null;
  text_preview: string | null;
  schemas: Schema[];
  metadata_summary: MetadataSummary;
}

function Dashboard() {
  const search = useSearch({ from: "/_layout/dashboard" });
  const url = (search as any)?.url as string | undefined;
  const [scanUrl, setScanUrl] = useState<string | null>(null);

  // Trigger scan when URL is available
  useEffect(() => {
    if (url) {
      setScanUrl(url);
    }
  }, [url]);

  // Fetch scan results
  const { data, isLoading, error } = useQuery<ScanResponse>({
    queryKey: ["scan", scanUrl],
    queryFn: async () => {
      if (!scanUrl) throw new Error("No URL provided");
      const response = await fetch("http://localhost:8000/api/v1/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: scanUrl }),
      });
      if (!response.ok) throw new Error("Failed to scan URL");
      return response.json();
    },
    enabled: !!scanUrl,
  });

  if (!url) {
    return (
      <Container maxW="4xl" py={8}>
        <Stack spacing={4}>
          <Heading size="md">Dashboard</Heading>
          <Text>No URL provided. Go back and enter a website.</Text>
        </Stack>
      </Container>
    );
  }

  return (
    <Container maxW="4xl" py={8}>
      <Stack spacing={6}>
        <Heading size="md">Analysis Results</Heading>

        <Box>
          <Text fontSize="sm" color="gray.500">
            Analyzing URL:
          </Text>
          <Code>{url}</Code>
        </Box>

        {isLoading && (
          <Box textAlign="center" py={8}>
            <Spinner size="xl" />
            <Text mt={4}>Scanning website...</Text>
          </Box>
        )}

        {error && (
          <Box borderWidth="1px" borderRadius="md" p={4} bg="red.50">
            <Text color="red.600">
              Error: {error instanceof Error ? error.message : "Failed to scan URL"}
            </Text>
          </Box>
        )}

        {data && (
          <VStack spacing={4} align="stretch">
            {/* Title */}
            <Box borderWidth="1px" borderRadius="md" p={4}>
              <Text fontSize="sm" fontWeight="bold" mb={2}>
                Title
              </Text>
              <Text>{data.title || "No title found"}</Text>
            </Box>

            {/* Description */}
            {data.description && (
              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Text fontSize="sm" fontWeight="bold" mb={2}>
                  Description
                </Text>
                <Text>{data.description}</Text>
              </Box>
            )}

            {/* Text Preview */}
            {data.text_preview && (
              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Text fontSize="sm" fontWeight="bold" mb={2}>
                  Readable Text Preview
                </Text>
                <Text fontSize="sm" color="gray.700">
                  {data.text_preview}
                </Text>
              </Box>
            )}

            {/* Metadata Summary */}
            <Box borderWidth="1px" borderRadius="md" p={4}>
              <Text fontSize="sm" fontWeight="bold" mb={3}>
                Structured Data Summary
              </Text>
              <HStack spacing={4}>
                <Badge colorScheme="blue">
                  JSON-LD: {data.metadata_summary.json_ld_count}
                </Badge>
                <Badge colorScheme="green">
                  Microdata: {data.metadata_summary.microdata_count}
                </Badge>
                <Badge colorScheme="purple">
                  OpenGraph: {data.metadata_summary.opengraph_count}
                </Badge>
              </HStack>
            </Box>

            {/* Schemas */}
            {data.schemas.length > 0 && (
              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Text fontSize="sm" fontWeight="bold" mb={3}>
                  Extracted Schemas ({data.schemas.length})
                </Text>
                <VStack spacing={3} align="stretch">
                  {data.schemas.map((schema, idx) => (
                    <Box
                      key={idx}
                      p={3}
                      bg="gray.50"
                      borderRadius="md"
                      fontSize="sm"
                    >
                      <Badge mb={2} colorScheme="cyan">
                        {schema.type}
                      </Badge>
                      <Code
                        display="block"
                        whiteSpace="pre"
                        p={2}
                        fontSize="xs"
                        overflowX="auto"
                      >
                        {JSON.stringify(schema.data, null, 2)}
                      </Code>
                    </Box>
                  ))}
                </VStack>
              </Box>
            )}
          </VStack>
        )}
      </Stack>
    </Container>
  );
}
