import { PlanScreen } from '@/features/plans';

export default async function PlanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PlanScreen planId={id} />;
}
