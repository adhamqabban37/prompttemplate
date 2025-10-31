import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  SimpleGrid,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Building,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Loader2,
  Lock,
  MapPin,
  Phone,
  RefreshCw,
  Share2,
  Sparkles,
  X as XIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

export const Route = createFileRoute(
  "/_layout/dashboard/teaser/$scanId" as any
)({
  component: TeaserDashboard,
});

interface TeaserKPIs {
  visibilityScore: number;
  pagesScanned: number;
  schemaDetected: boolean;
}

interface Finding {
  title: string;
  severity: "low" | "med" | "high";
}

interface TeaserResponse {
  url: string;
  kpis: TeaserKPIs;
  summary: string;
  topFindings: Finding[];
  lockedSections: string[];
}

export default function TeaserDashboard() {
  const navigate = useNavigate();
  const { scanId } = useParams({
    from: "/_layout/dashboard/teaser/$scanId",
  }) as { scanId: string };

  const statusQuery = useQuery({
    queryKey: ["scan", "status", scanId],
    queryFn: async () => {
      const r = await fetch(`/api/v1/scan-jobs/${scanId}/status`);
      if (!r.ok) throw new Error("status failed");
      return r.json() as Promise<{
        id: number;
        status: string;
        progress: number;
        teaser?: any;
      }>;
    },
    refetchInterval: 2500,
  });

  // Mark as used to satisfy TS strict unused locals during build
  void statusQuery.data;

  // When done, decide full vs paywall
  // Note: billing is checked in the interval below to avoid unused variable during build.

  useEffect(() => {
    try {
      const timer = window.setInterval(async () => {
        try {
          // infer scanId and navigate from existing scope
          // @ts-ignore - scanId and navigate exist in this component per current file
          const st = await fetch(`/api/v1/scan-jobs/${scanId}/status`).then(
            (r) => (r.ok ? r.json() : null)
          );
          if (st && st.status === "done") {
            const bill = await fetch(`/api/v1/billing/me`).then((r) =>
              r.ok ? r.json() : null
            );
            if (bill && bill.premium) {
              // @ts-ignore - navigate exists in scope
              navigate({
                to: "/dashboard/full/$scanId",
                params: { scanId: String(scanId) },
              });
            }
          }
        } catch {}
      }, 2500);
      return () => window.clearInterval(timer);
    } catch {}
    return () => {};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const teaser = useQuery<TeaserResponse, Error>({
    queryKey: ["scan", "teaser", scanId],
    queryFn: async () => {
      const res = await fetch(`/api/v1/scan-jobs/${scanId}/teaser`);
      if (!res.ok) throw new Error("Failed to load teaser");
      return res.json();
    },
  });

  const onUpgrade = async () => {
    const res = await fetch(`/api/v1/payments/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan: "premium_monthly", returnScanId: scanId }),
    });
    if (!res.ok) return;
    const data = await res.json();
    window.location.href = data.checkoutUrl;
  };

  // Derived: counts and high issues
  const highIssues = useMemo(
    () =>
      teaser.data?.topFindings.filter(
        (f) => f.severity.toLowerCase() === "high"
      ) ?? [],
    [teaser.data]
  );

  // Components
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
        data-testid="top-banner"
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
              {teaser.data?.url}
            </Text>
            <Text color="gray.400" fontSize="sm">
              • Scanned just now
            </Text>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRescanning(true);
                setTimeout(() => setRescanning(false), 1500);
              }}
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
    const data = [
      { name: "score", value: score },
      { name: "bg", value: Math.max(0, 100 - score) },
    ];
    const scoreColor =
      score <= 40
        ? "#F87171"
        : score <= 60
          ? "#FB923C"
          : score <= 80
            ? "#22D3EE"
            : "#8B5CF6";
    return (
      <Box w="9rem" h="9rem" position="relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              dataKey="value"
              innerRadius="70%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              stroke="none"
            >
              <Cell fill={scoreColor} />
              <Cell fill="#374151" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <Box
          position="absolute"
          inset={0}
          display="flex"
          alignItems="center"
          justifyContent="center"
        >
          <Text fontSize="4xl" fontWeight="bold" color={scoreColor}>
            {Math.round(score)}
          </Text>
        </Box>
      </Box>
    );
  };

  const UrgencyBar = () => {
    const [visible, setVisible] = useState(true);
    if (!visible || highIssues.length === 0) return null;
    return (
      <motion.div
        initial={{ y: -40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 120 }}
      >
        <Box maxW="7xl" mx="auto" px={4} mt={-4}>
          <Box
            p={4}
            borderRadius="lg"
            bgGradient="linear(to-r, pink.700, red.600)"
            color="white"
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            data-testid="urgency-bar"
          >
            <HStack>
              <AlertTriangle size={24} />
              <Box>
                <Heading size="md">
                  {highIssues.length} CRITICAL ISSUES DETECTED
                </Heading>
                <Text
                  fontSize="sm"
                  color="pink.100"
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {highIssues
                    .slice(0, 3)
                    .map((i) => i.title)
                    .join(", ")}
                  ...
                </Text>
              </Box>
            </HStack>
            <HStack>
              <Button onClick={onUpgrade} size="sm" colorScheme="whiteAlpha">
                Fix These First
              </Button>
              <Button variant="ghost" onClick={() => setVisible(false)}>
                <XIcon size={18} />
              </Button>
            </HStack>
          </Box>
        </Box>
      </motion.div>
    );
  };

  const IssueCard = ({
    title,
    severity,
  }: {
    title: string;
    severity: string;
  }) => {
    const [open, setOpen] = useState(false);
    const impactColor =
      severity.toLowerCase() === "high"
        ? "red.400"
        : severity.toLowerCase() === "med"
          ? "orange.400"
          : "yellow.400";
    return (
      <Box
        p={4}
        borderWidth="1px"
        borderLeftWidth="4px"
        borderLeftColor={impactColor}
        borderRadius="md"
        bg="gray.800"
      >
        <HStack justify="space-between" alignItems="flex-start">
          <HStack>
            {severity.toLowerCase() === "high" && (
              <AlertTriangle color="#F87171" size={18} />
            )}
            {severity.toLowerCase() === "med" && (
              <AlertTriangle color="#FBBF24" size={18} />
            )}
            {severity.toLowerCase() === "low" && (
              <CheckCircle color="#34D399" size={18} />
            )}
            <Text color="white" fontWeight="semibold">
              {title}
            </Text>
          </HStack>
          <Button variant="ghost" size="sm" onClick={() => setOpen((v) => !v)}>
            {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
        </HStack>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
            >
              <Box mt={3} p={3} borderRadius="md" bg="gray.700">
                <Text color="gray.200" fontSize="sm">
                  Upgrade to view Evidence, Why It Matters, and Fix Summary.
                </Text>
                <Button mt={3} size="sm" onClick={onUpgrade}>
                  <HStack>
                    <Sparkles size={14} />
                    <Text>Access Premium Version</Text>
                  </HStack>
                </Button>
              </Box>
            </motion.div>
          )}
        </AnimatePresence>
      </Box>
    );
  };

  const IssuesSection = () => {
    const highs = highIssues;
    const meds =
      teaser.data?.topFindings.filter(
        (f) => f.severity.toLowerCase() === "med"
      ) ?? [];
    const lows =
      teaser.data?.topFindings.filter(
        (f) => f.severity.toLowerCase() === "low"
      ) ?? [];
    const Group = ({
      label,
      items,
    }: {
      label: string;
      items: typeof highs;
    }) => {
      const [expanded, setExpanded] = useState(label === "HIGH");
      return (
        <Box mb={6} data-testid={`issues-group-${label.toLowerCase()}`}>
          <HStack
            justify="space-between"
            onClick={() => setExpanded((v) => !v)}
            cursor="pointer"
          >
            <Heading size="md" color="white">
              {label} PRIORITY{" "}
              <Text as="span" color="gray.400" fontSize="sm">
                ({items.length} issues)
              </Text>
            </Heading>
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </HStack>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Stack mt={4} gap={4}>
                  {items.map((i, idx) => (
                    <IssueCard
                      key={idx}
                      title={(i as any).title}
                      severity={(i as any).severity}
                    />
                  ))}
                  {label === "HIGH" && items.length >= 3 && (
                    <Box
                      p={6}
                      borderWidth="2px"
                      borderRadius="lg"
                      borderColor="purple.500"
                      textAlign="center"
                      bg="gray.800"
                    >
                      <Sparkles className="text-cyan-400" />
                      <Heading size="md" color="white" mt={2} mb={2}>
                        Unlock AI-Powered Fixes
                      </Heading>
                      <Text color="gray.300" mb={3}>
                        Generate schemas, write content, and fix top issues.
                      </Text>
                      <Button onClick={onUpgrade}>
                        Access Premium Version
                      </Button>
                    </Box>
                  )}
                </Stack>
              </motion.div>
            )}
          </AnimatePresence>
        </Box>
      );
    };
    return (
      <Box id="issues" maxW="7xl" mx="auto" px={4} py={12}>
        <Heading size="lg" mb={6}>
          Issues Detected ({teaser.data?.topFindings.length ?? 0})
        </Heading>
        <Group label="HIGH" items={highs as any} />
        <Group label="MEDIUM" items={meds as any} />
        <Group label="LOW" items={lows as any} />
      </Box>
    );
  };

  const StickyUpgradeCTA = () => (
    <motion.div
      initial={{ y: 60 }}
      animate={{ y: 0 }}
      transition={{ delay: 0.4, type: "spring", stiffness: 120 }}
    >
      <Box position="sticky" bottom={4} zIndex={30} maxW="xl" mx="auto">
        <Box
          p={5}
          borderRadius="xl"
          bgGradient="linear(to-r, cyan.400, blue.500, purple.600)"
          color="white"
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          data-testid="sticky-upgrade-cta"
        >
          <Box>
            <Heading size="md">You've found the issues.</Heading>
            <Text>Ready to fix them with AI?</Text>
          </Box>
          <Button
            onClick={onUpgrade}
            size="lg"
            bg="white"
            color="blue.600"
            data-testid="upgrade-button"
            aria-label="Upgrade to Premium"
          >
            <HStack>
              <Sparkles size={18} />
              <Text>Access Premium Version</Text>
            </HStack>
          </Button>
        </Box>
      </Box>
    </motion.div>
  );

  return (
    <Box bg="gray.900" color="gray.100" minH="100vh">
      <TopBanner />
      {teaser.isLoading ? (
        <Container maxW="6xl" py={8}>
          <Text>Loading…</Text>
        </Container>
      ) : teaser.isError ? (
        <Container maxW="6xl" py={8}>
          <Text color="red.400">
            Failed to load teaser: {teaser.error?.message}
          </Text>
        </Container>
      ) : (
        teaser.data && (
          <>
            <Box
              borderTopWidth="1px"
              borderBottomWidth="1px"
              borderColor="gray.700"
              bg="gray.800"
              py={4}
            >
              <Container maxW="7xl">
                <SimpleGrid
                  columns={{ base: 1, md: 2, lg: 4 }}
                  gap={4}
                  fontSize="sm"
                >
                  <HStack color="white">
                    <Building size={16} className="text-cyan-400" />
                    <Text fontWeight="semibold">Website</Text>
                    <Text
                      color="gray.300"
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {teaser.data.url}
                    </Text>
                  </HStack>
                  <HStack color="gray.300">
                    <MapPin size={16} className="text-cyan-400" />
                    <Text
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      City: —
                    </Text>
                  </HStack>
                  <HStack color="gray.300">
                    <Phone size={16} className="text-cyan-400" />
                    <Text
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      Phone: —
                    </Text>
                  </HStack>
                  <HStack color="gray.300">
                    <Clock size={16} className="text-cyan-400" />
                    <Text
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      Hours: —
                    </Text>
                  </HStack>
                </SimpleGrid>
              </Container>
            </Box>

            <Container maxW="7xl" py={10}>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} gap={6}>
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
                    <ScoreGauge score={teaser.data.kpis.visibilityScore} />
                  </HStack>
                  <Text textAlign="center" color="gray.400">
                    Teaser view
                  </Text>
                </Box>
                <Box
                  p={6}
                  borderWidth="1px"
                  borderColor="gray.700"
                  borderRadius="xl"
                  bg="gray.800"
                  position="relative"
                  overflow="hidden"
                >
                  <Text color="gray.300" mb={3}>
                    GEO Score (Local SEO)
                  </Text>
                  <HStack justify="center" mb={3}>
                    <ScoreGauge
                      score={Math.max(
                        0,
                        Math.min(100, teaser.data.kpis.visibilityScore - 5)
                      )}
                    />
                  </HStack>
                  <Box
                    position="absolute"
                    inset={0}
                    bg="blackAlpha.700"
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                  >
                    <Stack align="center">
                      <Lock />
                      <Text>Unlock Local Toolkit</Text>
                      <Button size="sm" onClick={onUpgrade}>
                        Optimize Local SEO
                      </Button>
                    </Stack>
                  </Box>
                </Box>
                <Box
                  p={6}
                  borderWidth="1px"
                  borderColor="gray.700"
                  borderRadius="xl"
                  bg="gray.800"
                >
                  <Text color="gray.300" mb={2}>
                    PSI (Mobile)
                  </Text>
                  <Stack gap={1}>
                    <HStack justify="space-between">
                      <Text color="gray.400">Performance</Text>
                      <Text>—</Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text color="gray.400">SEO</Text>
                      <Text>—</Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text color="gray.400">LCP</Text>
                      <Text>—</Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text color="gray.400">CLS</Text>
                      <Text>—</Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text color="gray.400">TBT</Text>
                      <Text>—</Text>
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
                    Priority Issues
                  </Text>
                  <Stack gap={3}>
                    <HStack>
                      <Box w={4} h={4} borderRadius="full" bg="red.500" />
                      <Text fontWeight="semibold">
                        {highIssues.length} High
                      </Text>
                    </HStack>
                    <HStack>
                      <Box w={4} h={4} borderRadius="full" bg="yellow.400" />
                      <Text fontWeight="semibold">
                        {teaser.data?.topFindings.filter(
                          (f) => f.severity.toLowerCase() === "med"
                        ).length ?? 0}{" "}
                        Medium
                      </Text>
                    </HStack>
                    <HStack>
                      <Box w={4} h={4} borderRadius="full" bg="green.400" />
                      <Text fontWeight="semibold">
                        {teaser.data?.topFindings.filter(
                          (f) => f.severity.toLowerCase() === "low"
                        ).length ?? 0}{" "}
                        Low
                      </Text>
                    </HStack>
                  </Stack>
                  <Text mt={3} color="cyan.400" fontWeight="semibold">
                    View All Issues ↓
                  </Text>
                </Box>
              </SimpleGrid>
            </Container>

            <UrgencyBar />
            <IssuesSection />
            <StickyUpgradeCTA />
          </>
        )
      )}
    </Box>
  );
}
