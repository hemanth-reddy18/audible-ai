import { redirect } from "next/navigation";

import { AudibleCallHub } from "@/components/home/AudibleCallHub";
import { getServerAccessToken, getServerAuthProvider } from "@/lib/auth/server";
import logger from "@/lib/logger";

export const dynamic = "force-dynamic";

export default async function Home() {
  logger.debug("[HomePage] Rendering Audible AI Single-Screen Call Hub");
  const authProvider = await getServerAuthProvider();
  const accessToken = await getServerAccessToken();

  if (!accessToken) {
    logger.debug("[HomePage] No access token found, redirecting to login");
    if (authProvider === "stack") {
      redirect("/handler/sign-in");
    } else {
      redirect("/auth/login");
    }
  }

  return <AudibleCallHub />;
}
