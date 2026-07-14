import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    service: "copilot-ui",
    version: "0.1.0",
  });
}
