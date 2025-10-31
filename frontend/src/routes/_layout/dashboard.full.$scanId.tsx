import {
  Box,
  Button,
  CircularProgress,
  CircularProgressLabel,
  Container,
  Heading,
  HStack,
  SimpleGrid,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  Share2,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

export const Route = createFileRoute("/_layout/dashboard/full/$scanId" as any)({
  component: FullDashboard,
});

interface FullResponse {
  visibility_score: number; // AEO score (0-100)
  geo_score: number; // GEO score (0-100)
  report_cards: Record<string, any>;
  business: {
    name?: string;
    phone?: string;
    address?: string;
    street_address?: string;
    city?: string;
    state?: string;
    postal_code?: string;
    nap_detected?: boolean;
    localbusiness_schema_detected?: boolean;
    organization_schema_detected?: boolean;
    google_business_hint?: boolean;
    apple_business_connect_hint?: boolean;
  };
  issues: string[];
  recommendations: string[];
  citations: string[];
  psi: {
    available: boolean;
    performance?: number;
    seo?: number;
    lcp_ms?: number;
    cls?: number;
    web_vitals?: Record<string, any>;
  };
  schema: any[];
}

function FullDashboard() {
  const { scanId } = Route.useParams();
  const navigate = useNavigate();

  // Optionally, ensure user is premium by attempting to fetch full
  const full = useQuery<FullResponse, Error>({
    queryKey: ["scan", "full", scanId],
    queryFn: async () => {
      const res = await fetch(`/api/v1/scan-jobs/${scanId}/full`);
      if (res.status === 402) {
        // Not premium => redirect to teaser
        navigate({ to: `/_layout/dashboard/teaser/${scanId}` });
        throw new Error("Premium required");
      }
      if (!res.ok) throw new Error("Failed to load full report");
      return res.json();
    },
  });

  // Helper: collapsible section
  const CollapsibleSection = ({
    title,
    children,
    defaultOpen = true,
  }: {
    title: string;
    children: React.ReactNode;
    defaultOpen?: boolean;
  }) => {
    const [open, setOpen] = useState(defaultOpen);
    return (
      <Box mb={4}>
        <HStack
          justify="space-between"
          cursor="pointer"
          onClick={() => setOpen(!open)}
          mb={2}
          p={2}
          borderRadius="md"
          _hover={{ bg: "gray.700" }}
        >
          <Text fontWeight="semibold" color="white">
            {title}
          </Text>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </HStack>
        {open && <Box pl={2}>{children}</Box>}
      </Box>
    );
  };

  // Helper: metric row
  const MetricRow = ({
    label,
    value,
    color,
  }: {
    label: string;
    value: string | number;
    color?: string;
  }) => (
    <HStack
      justify="space-between"
      py={2}
      borderBottomWidth="1px"
      borderColor="gray.700"
    >
      <Text color="gray.300">{label}</Text>
      <Text fontWeight="medium" color={color ?? "white"}>
        {value}
      </Text>
    </HStack>
  );

  const tabs = useMemo(
    () => [
      {
        key: "overview",
        label: "Overview",
        render: () => {
          const business = full.data?.business ?? {};
          const schema = full.data?.schema ?? [];
          return (
            <Stack gap={4}>
              <CollapsibleSection title="Business Information">
                {business.name && (
                  <MetricRow label="Name" value={business.name} />
                )}
                {business.phone && (
                  <MetricRow label="Phone" value={business.phone} />
                )}
                {business.address && (
                  <MetricRow label="Address" value={business.address} />
                )}
                {business.nap_detected && (
                  <MetricRow
                    label="NAP Detected"
                    value="Yes"
                    color="green.400"
                  />
                )}
                {business.localbusiness_schema_detected && (
                  <MetricRow
                    label="LocalBusiness Schema"
                    value="Present"
                    color="green.400"
                  />
                )}
                {business.organization_schema_detected && (
                  <MetricRow
                    label="Organization Schema"
                    value="Present"
                    color="green.400"
                  />
                )}
              </CollapsibleSection>
              <CollapsibleSection title="Structured Data">
                <Text color="gray.300" mb={2}>
                  {schema.length} schema items detected
                </Text>
                {schema.length > 0 ? (
                  schema.slice(0, 10).map((item: any, idx: number) => (
                    <Text key={idx} color="gray.400" fontSize="sm">
                      • {item["@type"] || "Unknown type"}
                    </Text>
                  ))
                ) : (
                  <Text color="orange.400" fontSize="sm">
                    No structured data found. Consider adding Schema.org markup.
                  </Text>
                )}
              </CollapsibleSection>
            </Stack>
          );
        },
      },
      {
        key: "vitals",
        label: "Core Web Vitals",
        render: () => {
          const psi = full.data?.psi ?? {};
          const lcp = psi.lcp_ms;
          const cls = psi.cls;

          // Helper to color-code vitals
          const getVitalColor = (metric: string, value: number | undefined) => {
            if (!value) return "gray.400";
            if (metric === "lcp") {
              if (value <= 2500) return "green.400";
              if (value <= 4000) return "orange.400";
              return "red.400";
            }
            if (metric === "cls") {
              if (value <= 0.1) return "green.400";
              if (value <= 0.25) return "orange.400";
              return "red.400";
            }
            return "gray.400";
          };

          return (
            <Stack gap={4}>
              {!psi.available ? (
                <Text color="gray.500">
                  PageSpeed Insights data not available for this scan.
                </Text>
              ) : (
                <>
                  <CollapsibleSection title="Performance Scores">
                    {psi.performance !== undefined && (
                      <MetricRow
                        label="Performance Score"
                        value={`${psi.performance}/100`}
                        color={
                          psi.performance >= 90
                            ? "green.400"
                            : psi.performance >= 50
                              ? "orange.400"
                              : "red.400"
                        }
                      />
                    )}
                    {psi.seo !== undefined && (
                      <MetricRow
                        label="SEO Score"
                        value={`${psi.seo}/100`}
                        color={
                          psi.seo >= 90
                            ? "green.400"
                            : psi.seo >= 50
                              ? "orange.400"
                              : "red.400"
                        }
                      />
                    )}
                  </CollapsibleSection>
                  <CollapsibleSection title="Web Vitals Metrics">
                    {lcp !== undefined && (
                      <MetricRow
                        label="LCP (Largest Contentful Paint)"
                        value={`${lcp}ms`}
                        color={getVitalColor("lcp", lcp)}
                      />
                    )}
                    {cls !== undefined && (
                      <MetricRow
                        label="CLS (Cumulative Layout Shift)"
                        value={cls.toFixed(3)}
                        color={getVitalColor("cls", cls)}
                      />
                    )}
                  </CollapsibleSection>
                </>
              )}
            </Stack>
          );
        },
      },
      {
        key: "recommendations",
        label: "Recommendations",
        render: () => {
          const recommendations = full.data?.recommendations ?? [];
          const issues = full.data?.issues ?? [];
          return (
            <Stack gap={4}>
              <CollapsibleSection title="Issues" defaultOpen={true}>
                {issues.length === 0 ? (
                  <Text color="green.400">No critical issues found!</Text>
                ) : (
                  issues.map((issue: string, idx: number) => (
                    <Box
                      key={idx}
                      p={3}
                      borderWidth="1px"
                      borderColor="red.700"
                      borderRadius="md"
                      bg="red.900"
                      mb={2}
                    >
                      <Text color="red.200" fontSize="sm">
                        ⚠️ {issue}
                      </Text>
                    </Box>
                  ))
                )}
              </CollapsibleSection>
              <CollapsibleSection title="Recommendations" defaultOpen={true}>
                {recommendations.length === 0 ? (
                  <Text color="gray.500">
                    No recommendations available yet.
                  </Text>
                ) : (
                  recommendations.map((rec: string, idx: number) => (
                    <Box
                      key={idx}
                      p={3}
                      borderWidth="1px"
                      borderColor="blue.700"
                      borderRadius="md"
                      bg="blue.900"
                      mb={2}
                    >
                      <Text color="blue.200" fontSize="sm">
                        💡 {rec}
                      </Text>
                    </Box>
                  ))
                )}
              </CollapsibleSection>
            </Stack>
          );
        },
      },
      {
        key: "citations",
        label: "Citations",
        render: () => {
          const citations = full.data?.citations ?? [];
          return (
            <Stack gap={4}>
              <Text color="gray.300" mb={2}>
                {citations.length} citation(s) found
              </Text>
              {citations.length === 0 ? (
                <Text color="gray.500">
                  No citations detected. Consider building local directory
                  presence.
                </Text>
              ) : (
                citations.map((citation: string, idx: number) => (
                  <Box
                    key={idx}
                    p={3}
                    borderWidth="1px"
                    borderColor="gray.700"
                    borderRadius="md"
                    bg="gray.800"
                  >
                    <Text color="gray.300" fontSize="sm">
                      📍 {citation}
                    </Text>
                  </Box>
                ))
              )}
            </Stack>
          );
        },
      },
    ],
    [full.data]
  );

  const [active, setActive] = useState("overview");

  const TopBanner = () => {
    const [isRescanning, setRescanning] = useState(false);
    const [shared, setShared] = useState(false);
    return (
      <Box
        position="sticky"
        top={0}
        zIndex={40}
        bg="gray.900"
        borderBottomWidth="1px"
        borderColor="purple.500"
        opacity={0.98}
        data-testid="full-top-banner"
      >
        <Box
          maxW="7xl"
          mx="auto"
          px={4}
          py={3}
          display="flex"
          alignItems="center"
          justifyContent="space-between"
        >
          <HStack gap={3}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => window.history.back()}
            >
              ←
            </Button>
            <Sparkles className="text-cyan-400" />
            <Text color="white" fontWeight="semibold">
              Scan Results
            </Text>
            <Text color="gray.400" fontSize="sm">
              • ID: {scanId.substring(0, 8)}
            </Text>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRescanning(true);
                setTimeout(() => setRescanning(false), 1500);
              }}
              title="Re-scan (coming soon)"
            >
              {isRescanning ? (
                <Loader2 className="animate-spin" size={16} />
              ) : (
                <RefreshCw size={16} />
              )}
            </Button>
          </HStack>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              navigator.clipboard.writeText(window.location.href);
              setShared(true);
              setTimeout(() => setShared(false), 1200);
            }}
          >
            <HStack>
              {shared ? <CheckCircle size={16} /> : <Share2 size={16} />}
              <Text>{shared ? "Copied!" : "Share"}</Text>
            </HStack>
          </Button>
        </Box>
      </Box>
    );
  };

  const ScoreGauge = ({ score }: { score: number }) => {
    const normalizedScore = Math.max(0, Math.min(100, score));
    const scoreColor =
      normalizedScore <= 40
        ? "red.400"
        : normalizedScore <= 60
          ? "orange.400"
          : normalizedScore <= 80
            ? "cyan.400"
            : "purple.400";
    return (
      <CircularProgress
        value={normalizedScore}
        size="144px"
        thickness="8px"
        color={scoreColor}
        trackColor="gray.700"
      >
        <CircularProgressLabel
          fontSize="4xl"
          fontWeight="bold"
          color={scoreColor}
        >
          {Math.round(normalizedScore)}
        </CircularProgressLabel>
      </CircularProgress>
    );
  };

  return (
    <Box bg="gray.900" color="gray.100" minH="100vh">
      <TopBanner />
      <Container maxW="7xl" py={8}>
        <Heading size="lg" mb={6}>
          Premium Dashboard
        </Heading>
        {full.isLoading ? (
          <Text>Loading…</Text>
        ) : full.isError ? (
          <Text>Error: {full.error?.message}</Text>
        ) : (
          <>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} gap={6} mb={8}>
              <Box
                p={6}
                borderWidth="1px"
                borderColor="gray.700"
                borderRadius="xl"
                bg="gray.800"
              >
                <Text color="gray.300" mb={3}>
                  AEO Score (AI Visibility)
                </Text>
                <HStack justify="center" mb={3}>
                  <ScoreGauge score={full.data?.visibility_score ?? 0} />
                </HStack>
                <Text textAlign="center" color="gray.400">
                  How well your content is optimized for AI search engines
                </Text>
              </Box>
              <Box
                p={6}
                borderWidth="1px"
                borderColor="gray.700"
                borderRadius="xl"
                bg="gray.800"
              >
                <Text color="gray.300" mb={3}>
                  GEO Score (Local SEO)
                </Text>
                <HStack justify="center" mb={3}>
                  <ScoreGauge score={full.data?.geo_score ?? 0} />
                </HStack>
                <Text textAlign="center" color="gray.400">
                  Local search visibility and business presence
                </Text>
              </Box>
              <Box
                p={6}
                borderWidth="1px"
                borderColor="gray.700"
                borderRadius="xl"
                bg="gray.800"
              >
                <Text color="gray.300" mb={2}>
                  PageSpeed Insights
                </Text>
                <Stack gap={1}>
                  <HStack justify="space-between">
                    <Text color="gray.400">Performance</Text>
                    <Text
                      color={
                        (full.data?.psi?.performance ?? 0) >= 90
                          ? "green.400"
                          : (full.data?.psi?.performance ?? 0) >= 50
                            ? "orange.400"
                            : "red.400"
                      }
                    >
                      {full.data?.psi?.performance ?? "—"}
                    </Text>
                  </HStack>
                  <HStack justify="space-between">
                    <Text color="gray.400">SEO</Text>
                    <Text
                      color={
                        (full.data?.psi?.seo ?? 0) >= 90
                          ? "green.400"
                          : (full.data?.psi?.seo ?? 0) >= 50
                            ? "orange.400"
                            : "red.400"
                      }
                    >
                      {full.data?.psi?.seo ?? "—"}
                    </Text>
                  </HStack>
                </Stack>
              </Box>
              <Box
                p={6}
                borderWidth="1px"
                borderColor="gray.700"
                borderRadius="xl"
                bg="gray.800"
              >
                <Text color="gray.300" mb={3}>
                  Issues Found
                </Text>
                <Text
                  fontSize="3xl"
                  fontWeight="bold"
                  textAlign="center"
                  color={
                    (full.data?.issues?.length ?? 0) === 0
                      ? "green.400"
                      : (full.data?.issues?.length ?? 0) <= 3
                        ? "orange.400"
                        : "red.400"
                  }
                >
                  {full.data?.issues?.length ?? 0}
                </Text>
                <Text textAlign="center" color="gray.400" mt={2}>
                  {(full.data?.issues?.length ?? 0) === 0
                    ? "Great job!"
                    : "Check recommendations"}
                </Text>
              </Box>
            </SimpleGrid>

            <Stack gap={4}>
              <Box display="flex" flexWrap="wrap" gap={2}>
                {tabs.map((t) => (
                  <Button
                    key={t.key}
                    onClick={() => setActive(t.key)}
                    colorScheme={active === t.key ? "purple" : undefined}
                  >
                    {t.label}
                  </Button>
                ))}
              </Box>
              <Box
                borderWidth="1px"
                borderRadius="md"
                p={4}
                bg="gray.800"
                borderColor="gray.700"
              >
                {tabs.find((t) => t.key === (active as string))?.render()}
              </Box>
            </Stack>
          </>
        )}
      </Container>
    </Box>
  );
}
