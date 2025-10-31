import {
  Badge,
  Box,
  Button,
  Circle,
  Code,
  Container,
  Flex,
  Grid,
  Heading,
  HStack,
  Input,
  Link,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import {
  createFileRoute,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toaster } from "@/components/ui/toaster";

export const Route = createFileRoute("/_layout/dashboard")({
  component: Dashboard,
});

interface Weakness {
  title: string;
  impact: string;
  evidence: string[];
  fix_summary: string;
}

interface Keyphrase {
  phrase: string;
  weight: number;
  intent: string;
}

interface AnalyzeResponse {
  target_url: string;
  status: string;
  page_title: string | null;
  meta_description: string | null;
  aeo_score: number;
  geo_score: number;
  weaknesses: Weakness[];
  recommendations: string[];
  keyphrases: Keyphrase[];
  psi_snapshot: {
    performance: number | null;
    seo: number | null;
    web_vitals: {
      lcp_ms?: number;
      cls?: number;
    };
  };
  nap: {
    name: string | null;
    address: string | null;
    phone: string | null;
  };
  structured_data_summary: {
    json_ld_count: number;
    microdata_count: number;
    opengraph_count: number;
    missing_elements: string[];
  };
  timings: {
    total_ms: number;
  };
}

// Presentational atoms to apply new layout visuals without changing behavior
function HeaderNav() {
  return (
    <Box
      as="header"
      position="sticky"
      top={0}
      zIndex={10}
      bg="gray.900"
      borderBottomWidth="1px"
      borderColor="whiteAlpha.300"
    >
      <Container maxW="7xl" py={3}>
        <Flex align="center" justify="space-between">
          <HStack gap={2}>
            <Box
              w={6}
              h={6}
              bgGradient="linear(to-r, cyan.400, purple.600)"
              borderRadius="md"
            />
            <Heading size="md" color="white">
              XenlixAI
            </Heading>
          </HStack>
          <HStack
            display={{ base: "none", md: "flex" }}
            gap={6}
            color="gray.300"
          >
            <Link href="#overview" _hover={{ color: "white" }}>
              Overview
            </Link>
            <Link href="#issues" _hover={{ color: "white" }}>
              Issues
            </Link>
            <Link href="#recommendations" _hover={{ color: "white" }}>
              Recommendations
            </Link>
            <Link href="#schema" _hover={{ color: "white" }}>
              Schema
            </Link>
          </HStack>
          <HStack gap={3}>
            <Button variant="ghost" size="sm">
              Log In
            </Button>
            <Button colorScheme="purple" size="sm">
              Start Free Scan
            </Button>
          </HStack>
        </Flex>
      </Container>
    </Box>
  );
}

function HeroStrip({
  inputUrl,
  setInputUrl,
  onAnalyze,
}: {
  inputUrl: string;
  setInputUrl: (v: string) => void;
  onAnalyze: () => void;
}) {
  return (
    <Box
      position="relative"
      bg="gray.900"
      color="white"
      py={{ base: 10, md: 16 }}
    >
      <Container maxW="4xl" textAlign="center">
        <Text fontSize="sm" color="gray.300" mb={3}>
          Trusted by 10,000+ businesses
        </Text>
        <Heading as="h1" size={{ base: "xl", md: "2xl" }} mb={3}>
          Your Website's
          <Box
            as="span"
            bgClip="text"
            bgGradient="linear(to-r, cyan.400, purple.600)"
            ml={2}
          >
            AI Visibility Score
          </Box>
        </Heading>
        <Text color="gray.300" maxW="2xl" mx="auto" mb={6}>
          See how AI engines understand your business—and get an action plan to
          fix gaps.
        </Text>
        <HStack
          mx="auto"
          maxW="xl"
          bg="blackAlpha.500"
          borderWidth="1px"
          borderColor="whiteAlpha.200"
          borderRadius="md"
          p={2}
          gap={2}
        >
          <Input
            placeholder="https://yourwebsite.com"
            value={inputUrl}
            onChange={(e) => setInputUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onAnalyze();
            }}
            bg="transparent"
            color="white"
            _placeholder={{ color: "whiteAlpha.600" }}
          />
          <Button colorScheme="purple" onClick={onAnalyze}>
            Analyze
          </Button>
        </HStack>
        <HStack justify="center" gap={6} mt={4} color="gray.400" fontSize="sm">
          <Text>Free instant scan</Text>
          <Text>No signup required</Text>
          <Text>~60s results</Text>
        </HStack>
      </Container>
    </Box>
  );
}

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <Box
      borderWidth="1px"
      borderRadius="lg"
      p={4}
      bg="white"
      _dark={{ bg: "gray.800" }}
    >
      <Text fontSize="sm" color="gray.500">
        {label}
      </Text>
      <Heading size="lg" color={color}>
        {value}
      </Heading>
    </Box>
  );
}

function Dashboard() {
  const search = useSearch({ from: "/_layout/dashboard" });
  const url = (search as any)?.url as string | undefined;
  const navigate = useNavigate();
  const [scanUrl, setScanUrl] = useState<string | null>(null);
  const [inputUrl, setInputUrl] = useState<string>(url || "");

  useEffect(() => {
    if (url) setScanUrl(url);
    if (url) setInputUrl(url);
  }, [url]);

  const normalizeUrl = (u: string) => {
    const trimmed = (u || "").trim();
    if (!trimmed) return "";
    if (/^https?:\/\//i.test(trimmed)) return trimmed;
    return `https://${trimmed}`;
  };

  const handleAnalyze = () => {
    const n = normalizeUrl(inputUrl);
    if (!n) {
      toaster.create({ title: "Enter a URL", type: "warning", duration: 2500 });
      return;
    }
    // Preserve existing navigation contract
    navigate({ to: "/dashboard", search: { url: n } });
  };

  const { data, isLoading, error } = useQuery<AnalyzeResponse, Error>({
    queryKey: ["analyze", scanUrl],
    queryFn: async () => {
      if (!scanUrl) throw new Error("No URL provided");
      // Use relative URL so Vite proxy handles it
      const response = await fetch(`/api/v1/analyze-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: scanUrl, free_test_mode: true }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Analysis failed: ${response.status} ${errorText}`);
      }
      return response.json();
    },
    enabled: !!scanUrl,
  });

  useEffect(() => {
    if (error) {
      toaster.create({
        title: "Analysis failed",
        description: error.message,
        type: "error",
        duration: 4000,
      });
    }
  }, [error]);

  const getScoreColor = (score: number): string => {
    if (score >= 80) return "green.500";
    if (score >= 60) return "yellow.500";
    if (score >= 40) return "orange.500";
    return "red.500";
  };

  const ScoreCircle = ({ score, label }: { score: number; label: string }) => {
    const radius = 50;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;
    const ringBg = "#E2E8F0"; // gray.200
    const ringFg = "#2D3748"; // gray.700

    return (
      <VStack gap={2}>
        <Box position="relative" width="140px" height="140px">
          <svg
            width="140"
            height="140"
            style={{ transform: "rotate(-90deg)" }}
            role="img"
            aria-label={`${label}: ${score}`}
          >
            <title>{`${label}: ${score}`}</title>
            <circle
              cx="70"
              cy="70"
              r={radius}
              stroke={ringBg}
              strokeWidth="10"
              fill="none"
            />
            <circle
              cx="70"
              cy="70"
              r={radius}
              stroke={ringFg}
              strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              fill="none"
            />
          </svg>
          <Box
            position="absolute"
            top="50%"
            left="50%"
            transform="translate(-50%, -50%)"
            textAlign="center"
          >
            <Text fontSize="3xl" fontWeight="bold">
              {score}
            </Text>
            <Text fontSize="xs" color="gray.500">
              / 100
            </Text>
          </Box>
        </Box>
        <Text fontSize="sm" fontWeight="medium" textAlign="center">
          {label}
        </Text>
      </VStack>
    );
  };

  // When no URL is provided, show the new hero layout for starting a scan
  if (!url) {
    return (
      <Box>
        <HeaderNav />
        <HeroStrip
          inputUrl={inputUrl}
          setInputUrl={setInputUrl}
          onAnalyze={handleAnalyze}
        />
        <Container maxW="6xl" py={10}>
          <Stack gap={6}>
            <Heading size="md" color="gray.600">
              AEO/GEO Analysis Dashboard
            </Heading>
            <Text color="gray.600">
              Paste a URL above and hit Analyze to view results.
            </Text>
          </Stack>
        </Container>
      </Box>
    );
  }

  return (
    <Box>
      <HeaderNav />
      <Container maxW="7xl" py={8}>
        <Stack gap={6}>
          {/* Header area with URL and inline input (kept behavior) */}
          <Box>
            <Text fontSize="sm" color="gray.500" mb={2}>
              Analyzing
            </Text>
            <HStack gap={3} align="center" flexWrap="wrap">
              <Code fontSize="sm" px={3} py={2}>
                {url}
              </Code>
              <HStack gap={2}>
                <Input
                  size="sm"
                  width={{ base: "full", md: "360px" }}
                  value={inputUrl}
                  onChange={(e) => setInputUrl(e.target.value)}
                  placeholder="https://example.com/page"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAnalyze();
                  }}
                />
                <Button size="sm" colorScheme="purple" onClick={handleAnalyze}>
                  Analyze
                </Button>
              </HStack>
            </HStack>
          </Box>

          {/* Overview KPIs */}
          <Box id="overview">
            {isLoading ? (
              <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={4}>
                <Skeleton height="120px" />
                <Skeleton height="120px" />
                <Skeleton height="120px" />
                <Skeleton height="120px" />
              </SimpleGrid>
            ) : (
              data && (
                <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={4}>
                  <KpiCard
                    label="AEO Score"
                    value={data.aeo_score}
                    color={getScoreColor(data.aeo_score)}
                  />
                  <KpiCard
                    label="GEO Score"
                    value={data.geo_score}
                    color={getScoreColor(data.geo_score)}
                  />
                  {typeof data.psi_snapshot.performance === "number" && (
                    <KpiCard
                      label="PSI Performance"
                      value={Math.round(data.psi_snapshot.performance)}
                      color={getScoreColor(data.psi_snapshot.performance)}
                    />
                  )}
                  {typeof data.psi_snapshot.seo === "number" && (
                    <KpiCard
                      label="PSI SEO"
                      value={Math.round(data.psi_snapshot.seo)}
                      color={getScoreColor(data.psi_snapshot.seo)}
                    />
                  )}
                </SimpleGrid>
              )
            )}
          </Box>

          {/* Title & Meta Card */}
          {isLoading ? (
            <Skeleton height="140px" />
          ) : (
            data && (
              <Box borderWidth="1px" borderRadius="lg" p={5}>
                <Heading size="sm" color="gray.600" mb={2}>
                  Page Title
                </Heading>
                <Text fontSize="lg" fontWeight="medium">
                  {data.page_title || "(No title found)"}
                </Text>
                {data.meta_description && (
                  <Box mt={4}>
                    <Text
                      fontSize="sm"
                      fontWeight="bold"
                      color="gray.600"
                      mb={1}
                    >
                      Meta Description
                    </Text>
                    <Text fontSize="sm" color="gray.700">
                      {data.meta_description}
                    </Text>
                  </Box>
                )}
              </Box>
            )
          )}

          {/* Score Circles */}
          {isLoading ? (
            <Skeleton height="220px" />
          ) : (
            data && (
              <Box borderWidth="1px" borderRadius="lg" p={6}>
                <Heading size="sm" mb={4}>
                  Visibility Scores
                </Heading>
                <Grid
                  templateColumns="repeat(auto-fit, minmax(200px, 1fr))"
                  gap={8}
                  justifyItems="center"
                >
                  <ScoreCircle
                    score={data.aeo_score}
                    label="AEO (AI Visibility)"
                  />
                  <ScoreCircle score={data.geo_score} label="GEO (Local SEO)" />
                  {typeof data.psi_snapshot.performance === "number" && (
                    <ScoreCircle
                      score={Math.round(data.psi_snapshot.performance)}
                      label="Performance (PSI)"
                    />
                  )}
                  {typeof data.psi_snapshot.seo === "number" && (
                    <ScoreCircle
                      score={Math.round(data.psi_snapshot.seo)}
                      label="SEO (PSI)"
                    />
                  )}
                </Grid>
              </Box>
            )
          )}

          {/* Issues */}
          {isLoading ? (
            <Skeleton height="240px" />
          ) : (
            data &&
            data.weaknesses.length > 0 && (
              <Box id="issues">
                <Box borderWidth="1px" borderRadius="lg" p={5}>
                  <Heading size="sm" mb={3}>
                    Issues Found
                  </Heading>
                  <VStack gap={3} align="stretch">
                    {data.weaknesses.map(
                      (weakness: Weakness, index: number) => (
                        <Box
                          key={index}
                          p={4}
                          borderWidth="1px"
                          borderRadius="md"
                          borderLeftWidth="4px"
                          borderLeftColor={
                            weakness.impact === "high"
                              ? "red.500"
                              : weakness.impact === "med"
                                ? "orange.500"
                                : "yellow.500"
                          }
                          bg="gray.50"
                        >
                          {/* TODO: consider dark mode bg */}
                          <HStack mb={2} align="start" justify="space-between">
                            <HStack>
                              <Badge
                                colorScheme={
                                  weakness.impact === "high"
                                    ? "red"
                                    : weakness.impact === "med"
                                      ? "orange"
                                      : "yellow"
                                }
                              >
                                {weakness.impact.toUpperCase()}
                              </Badge>
                              <Text fontWeight="bold">{weakness.title}</Text>
                            </HStack>
                          </HStack>
                          <Text fontSize="sm" color="gray.700" mb={2}>
                            <strong>Fix:</strong> {weakness.fix_summary}
                          </Text>
                          {weakness.evidence.length > 0 && (
                            <Text fontSize="xs" color="gray.500">
                              Evidence: {weakness.evidence.join(", ")}
                            </Text>
                          )}
                        </Box>
                      )
                    )}
                  </VStack>
                </Box>
              </Box>
            )
          )}

          {/* Recommendations */}
          {isLoading ? (
            <Skeleton height="200px" />
          ) : (
            data &&
            data.recommendations.length > 0 && (
              <Box id="recommendations">
                <Box
                  borderWidth="1px"
                  borderRadius="lg"
                  p={5}
                  bg="blue.50"
                  borderColor="blue.200"
                >
                  <Heading size="sm" mb={3}>
                    Recommendations
                  </Heading>
                  <VStack gap={2} align="stretch">
                    {data.recommendations.map((rec: string, index: number) => (
                      <HStack key={index} align="start">
                        <Circle
                          size="6"
                          bg="blue.500"
                          color="white"
                          fontSize="xs"
                          fontWeight="bold"
                          flexShrink={0}
                        >
                          {index + 1}
                        </Circle>
                        <Text fontSize="sm">{rec}</Text>
                      </HStack>
                    ))}
                  </VStack>
                </Box>
              </Box>
            )
          )}

          {/* Keyphrases */}
          {isLoading ? (
            <Skeleton height="160px" />
          ) : (
            data &&
            data.keyphrases.length > 0 && (
              <Box borderWidth="1px" borderRadius="lg" p={5}>
                <Heading size="sm" mb={3}>
                  Key Topics
                </Heading>
                <HStack gap={2} flexWrap="wrap">
                  {data.keyphrases
                    .slice(0, 8)
                    .map((kp: Keyphrase, index: number) => (
                      <Badge
                        key={index}
                        colorScheme="purple"
                        px={3}
                        py={1}
                        fontSize="sm"
                      >
                        {kp.phrase} ({kp.intent})
                      </Badge>
                    ))}
                </HStack>
              </Box>
            )
          )}

          {/* NAP */}
          {isLoading ? (
            <Skeleton height="140px" />
          ) : (
            data &&
            (data.nap.name || data.nap.address || data.nap.phone) && (
              <Box borderWidth="1px" borderRadius="lg" p={5}>
                <Heading size="sm" mb={3}>
                  Business Information (NAP)
                </Heading>
                <VStack gap={2} align="stretch">
                  {data.nap.name && (
                    <Text>
                      <strong>Name:</strong> {data.nap.name}
                    </Text>
                  )}
                  {data.nap.address && (
                    <Text>
                      <strong>Address:</strong> {data.nap.address}
                    </Text>
                  )}
                  {data.nap.phone && (
                    <Text>
                      <strong>Phone:</strong> {data.nap.phone}
                    </Text>
                  )}
                </VStack>
              </Box>
            )
          )}

          {/* Schema Summary */}
          {isLoading ? (
            <Skeleton height="180px" />
          ) : (
            data && (
              <Box id="schema">
                <Box borderWidth="1px" borderRadius="lg" p={5}>
                  <Heading size="sm" mb={3}>
                    Structured Data
                  </Heading>
                  <HStack gap={4} mb={3} flexWrap="wrap">
                    <Badge colorScheme="blue">
                      JSON-LD: {data.structured_data_summary.json_ld_count}
                    </Badge>
                    <Badge colorScheme="green">
                      Microdata: {data.structured_data_summary.microdata_count}
                    </Badge>
                    <Badge colorScheme="purple">
                      OpenGraph: {data.structured_data_summary.opengraph_count}
                    </Badge>
                  </HStack>
                  {data.structured_data_summary.missing_elements.length > 0 && (
                    <Box mt={3}>
                      <Text
                        fontSize="sm"
                        fontWeight="bold"
                        color="gray.600"
                        mb={2}
                      >
                        Missing Elements
                      </Text>
                      <HStack gap={2} flexWrap="wrap">
                        {data.structured_data_summary.missing_elements.map(
                          (elem: string, index: number) => (
                            <Badge
                              key={index}
                              colorScheme="red"
                              variant="outline"
                            >
                              {elem}
                            </Badge>
                          )
                        )}
                      </HStack>
                    </Box>
                  )}
                </Box>
              </Box>
            )
          )}

          {/* Core Web Vitals */}
          {isLoading ? (
            <Skeleton height="180px" />
          ) : (
            data?.psi_snapshot.web_vitals && (
              <Box borderWidth="1px" borderRadius="lg" p={5}>
                <Heading size="sm" mb={3}>
                  Core Web Vitals
                </Heading>
                <Grid
                  templateColumns="repeat(auto-fit, minmax(150px, 1fr))"
                  gap={4}
                >
                  {data.psi_snapshot.web_vitals.lcp_ms && (
                    <Box
                      textAlign="center"
                      p={3}
                      borderWidth="1px"
                      borderRadius="md"
                    >
                      <Text
                        fontSize="2xl"
                        fontWeight="bold"
                        color={
                          data.psi_snapshot.web_vitals.lcp_ms < 2500
                            ? "green.500"
                            : "red.500"
                        }
                      >
                        {(data.psi_snapshot.web_vitals.lcp_ms / 1000).toFixed(
                          2
                        )}
                        s
                      </Text>
                      <Text fontSize="xs" color="gray.600">
                        LCP (target: &lt;2.5s)
                      </Text>
                    </Box>
                  )}
                  {data.psi_snapshot.web_vitals.cls !== undefined && (
                    <Box
                      textAlign="center"
                      p={3}
                      borderWidth="1px"
                      borderRadius="md"
                    >
                      <Text
                        fontSize="2xl"
                        fontWeight="bold"
                        color={
                          data.psi_snapshot.web_vitals.cls < 0.1
                            ? "green.500"
                            : "orange.500"
                        }
                      >
                        {data.psi_snapshot.web_vitals.cls.toFixed(3)}
                      </Text>
                      <Text fontSize="xs" color="gray.600">
                        CLS (target: &lt;0.1)
                      </Text>
                    </Box>
                  )}
                </Grid>
              </Box>
            )
          )}

          {/* Timing */}
          {isLoading
            ? null
            : data && (
                <Box borderWidth="1px" borderRadius="lg" p={3} bg="gray.50">
                  {/* TODO: consider dark mode bg */}
                  <Text fontSize="xs" color="gray.600" textAlign="center">
                    ⏱️ Analysis completed in{" "}
                    {(data.timings.total_ms / 1000).toFixed(2)}s
                  </Text>
                </Box>
              )}
        </Stack>
      </Container>
    </Box>
  );
}

export default Dashboard;
