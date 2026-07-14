"use client";

import { create } from "zustand";

import {
  deleteTenant,
  getSettings,
  updateAvatar,
  updateSettings,
} from "@/features/settings/api/settings";
import type { TenantSettings } from "@/features/settings/model/types";

interface SettingsState {
  settings: TenantSettings | null;
  isLoading: boolean;
  error: string | null;

  loadSettings: () => Promise<void>;
  updateSettings: (name: string) => Promise<void>;
  uploadAvatar: (file: File) => Promise<void>;
  deleteTenant: () => Promise<boolean>;
  reset: () => void;
}

const initialState = {
  settings: null,
  isLoading: false,
  error: null,
};

export const useSettingsStore = create<SettingsState>((set) => ({
  ...initialState,

  loadSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      set({ settings: await getSettings() });
    } catch (error) {
      set({
        error:
          error instanceof Error ? error.message : "Error loading settings",
      });
    } finally {
      set({ isLoading: false });
    }
  },

  updateSettings: async (name) => {
    set({ settings: await updateSettings(name) });
  },

  uploadAvatar: async (file) => {
    set({ settings: await updateAvatar(file) });
  },

  deleteTenant: async () => {
    const response = await deleteTenant();
    return response.success;
  },

  reset: () => set(initialState),
}));
