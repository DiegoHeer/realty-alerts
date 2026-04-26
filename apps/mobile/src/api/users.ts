import { api } from "./client";
import type { UserProfile, UserUpdate } from "@/types";

export async function getMe(): Promise<UserProfile> {
  return api.get<UserProfile>("/api/v1/users/me");
}

export async function updateMe(data: UserUpdate): Promise<UserProfile> {
  return api.patch<UserProfile>("/api/v1/users/me", data);
}
