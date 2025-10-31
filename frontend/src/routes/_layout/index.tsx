import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/_layout/")({
  component: Home,
});

function Home() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  // Using a simple alert for errors to avoid dependency on toasts

  // Start scan mutation
  const startScan = useMutation<{ id: number }, Error, { url: string }>({
    mutationKey: ["scan", "start"],
    mutationFn: async (vars) => {
      const res = await fetch(`/api/v1/scan-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: vars.url }),
      });
      if (!res.ok) {
        let detail = "Failed to start scan";
        try {
          const j = await res.json();
          detail = j?.detail || detail;
        } catch {}
        throw new Error(detail);
      }
      return res.json() as Promise<{ id: number }>;
    },
    onSuccess: (data) => {
      // Immediately go to analyzing page
      navigate({
        to: "/dashboard/analyzing/$scanId",
        params: { scanId: String(data.id) },
      });
    },
    onError: (error) => {
      alert((error as Error).message || "Could not start scan");
    },
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    await startScan.mutateAsync({ url });
  };

  return (
    <Container maxW="lg" py={16}>
      <Stack gap={6}>
        <Heading size="lg">Xenlixai</Heading>
        <Box as="form" onSubmit={onSubmit}>
          <Stack direction={{ base: "column", md: "row" }} gap={3}>
            <Input
              placeholder="Enter your website URL (https://example.com)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <Button
              type="submit"
              colorScheme="blue"
              isLoading={startScan.isPending}
            >
              Analyze
            </Button>
          </Stack>
        </Box>
      </Stack>
    </Container>
  );
}
