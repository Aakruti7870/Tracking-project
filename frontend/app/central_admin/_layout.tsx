import React from "react";
import { StaffTabs } from "@/src/screens/StaffTabs";
import { TabDef } from "@/src/components/GlassTabBar";

const TABS: TabDef[] = [
  { name: "index", label: "Home", icon: "home-outline", active: "home" },
  { name: "plants", label: "Plants", icon: "business-outline", active: "business" },
  { name: "users", label: "Users", icon: "people-outline", active: "people" },
  { name: "more", label: "More", icon: "grid-outline", active: "grid" },
];

export default function Layout() {
  return <StaffTabs role="central_admin" tabs={TABS} />;
}
