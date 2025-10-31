import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { ErrorBoundary } from "react-error-boundary";
import { ApiError, OpenAPI } from "./client";
import { CustomProvider } from "./components/ui/provider";
import { routeTree } from "./routeTree.gen";
import {
  Box,
  Center,
  Heading,
  Spinner,
  Stack,
  Text,
  Button,
} from "@chakra-ui/react";

OpenAPI.BASE = import.meta.env.VITE_API_URL;
OpenAPI.TOKEN = async () => {
  return localStorage.getItem("access_token") || "";
};

const handleApiError = (error: Error) => {
  if (error instanceof ApiError && [401, 403].includes(error.status)) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  }
};
const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handleApiError,
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
});

const router = createRouter({ routeTree });
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

function LoadingFallback() {
  return (
    <Center h="100vh">
      <Stack align="center" gap={4}>
        <Spinner size="xl" color="ui.main" />
        <Heading size="md">Loading XenlixAI...</Heading>
        <Text color="gray.500">Connecting to backend...</Text>
      </Stack>
    </Center>
  );
}

function ErrorFallback({
  error,
  resetErrorBoundary,
}: {
  error: Error;
  resetErrorBoundary: () => void;
}) {
  return (
    <Center h="100vh">
      <Stack align="center" gap={4} maxW="md" textAlign="center">
        <Heading size="lg" color="red.500">
          Oops! Something went wrong
        </Heading>
        <Box bg="red.50" p={4} borderRadius="md" w="full">
          <Text fontFamily="mono" fontSize="sm" color="red.700">
            {error.message || "Unknown error"}
          </Text>
        </Box>
        <Text color="gray.600">
          The application encountered an error. Please try refreshing the page
          or contact support if the issue persists.
        </Text>
        <Button onClick={resetErrorBoundary} colorScheme="blue">
          Try Again
        </Button>
      </Stack>
    </Center>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <CustomProvider>
        <QueryClientProvider client={queryClient}>
          <Suspense fallback={<LoadingFallback />}>
            <RouterProvider router={router} />
          </Suspense>
        </QueryClientProvider>
      </CustomProvider>
    </ErrorBoundary>
  </StrictMode>
);
