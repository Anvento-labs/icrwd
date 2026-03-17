import CopilotSidebar from '../components/CopilotSidebar';
export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-[#0b0b0b] p-8 text-white">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-4 text-3xl font-bold">Welcome to CRWD</h1>
        <p className="text-gray-400">
          Your dashboard content lives here. Click the yellow button in the bottom right to open the Copilot!
        </p>
      </div>

      <CopilotSidebar />
    </div>
  );
}