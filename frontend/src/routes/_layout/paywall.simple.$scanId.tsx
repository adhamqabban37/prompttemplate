import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_layout/paywall/simple/$scanId')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_layout/paywall/simple/$scanId"!</div>
}
