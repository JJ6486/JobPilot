"use client";

import { use } from "react";

import { ApplicationView } from "@/components/application/application-view";

export default function ApplicationPage({ params }: PageProps<"/applications/[id]">) {
  const { id } = use(params);
  return <ApplicationView id={Number(id)} />;
}
