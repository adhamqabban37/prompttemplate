import {
  Box,
  Button,
  Container,
  Heading,
  Progress,
  Stack,
  Text,
} from "@chakra-ui/react";
import {
  createFileRoute,
  useParams,
  useRouter,
  useSearch,
} from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";

type StatusShape = {
  id: string;
  status: "pending" | "processing" | "done" | "failed" | string;
  error: string | null;
  teaser: {
    title?: string;
    schema_count?: number;
    has_schema?: boolean;
  } | null;
  progress?: number | null;
};

export const Route = createFileRoute(
  "/_layout/dashboard/analyzing/$scanId" as any
)({
  component: AnalyzingPage,
});

export default function AnalyzingPage() {
  const { scanId } = useParams({
    from: "/_layout/dashboard/analyzing/$scanId",
  }) as { scanId: string };
  const router = useRouter();
  const search = useSearch({
    from: "/_layout/dashboard/analyzing/$scanId",
  }) as { url?: string };
  const [data, setData] = useState<StatusShape | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const progress = Math.max(0, Math.min(100, Number(data?.progress ?? 10)));
  const showUrl = useMemo(() => search?.url || "", [search?.url]);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/v1/scan-jobs/${scanId}/status`);
        if (!res.ok) {
          setError("Could not reach backend.");
          return;
        }
        const json: StatusShape = await res.json();
        if (cancelled) return;
        setData(json);
        if (json.status === "done") {
          router.navigate({ to: "/dashboard/$scanId", params: { scanId } });
          return;
        }
        if (json.status === "failed") {
          // stop polling
          return;
        }
        // keep polling
        timerRef.current = window.setTimeout(
          fetchStatus,
          2000
        ) as unknown as number;
      } catch (e) {
        setError("Network error");
      }
    };
    fetchStatus();
    return () => {
      cancelled = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [scanId, router]);

  // Error view (backend reported failed or network error)
  if (error || data?.status === "failed") {
    const message = error || data?.error || "Could not analyze this URL";
    return (
      <Container maxW="lg" py={12}>
        <Stack gap={4}>
          <Heading size="md">Scan failed</Heading>
          <Box borderWidth="1px" borderRadius="md" p={4} bg="red.50">
            <Text color="red.700">{message}</Text>
          </Box>
          <Button
            onClick={() => router.navigate({ to: "/" })}
            colorScheme="blue"
          >
            Try another URL
          </Button>
        </Stack>
      </Container>
    );
  }

  // Pending / Processing view
  return (
    <Container maxW="lg" py={12}>
      <Stack gap={6}>
        <Heading size="lg">Analyzing this page…</Heading>
        {showUrl && (
          <Box>
            <Text color="gray.500" fontSize="sm">
              URL
            </Text>
            <Text fontFamily="mono" lineClamp={2}>
              {showUrl}
            </Text>
          </Box>
        )}
        <Box>
          <Text mb={2}>Progress</Text>
          <Progress value={progress} colorScheme="purple" borderRadius="sm" />
          <Text color="gray.500" fontSize="sm" mt={2}>
            Status: {data?.status || "pending"}
          </Text>
        </Box>
        <Box>
          {data?.teaser?.title ? (
            <Text>Detected title: {data.teaser.title}</Text>
          ) : (
            <Text color="gray.500">Detecting title…</Text>
          )}
          {data?.teaser?.has_schema === false && (
            <Text color="gray.500">No schema yet — still checking…</Text>
          )}
        </Box>
        <Text color="gray.500" fontSize="sm">
          This will automatically advance when analysis completes.
        </Text>
      </Stack>
    </Container>
  );
}
