"use client";

import { create } from "zustand";
import { useSessionStore } from "@/features/auth";
import {
  getProfile,
  profileErrorMessage,
  updatePassword as updatePasswordRequest,
  updateProfile as updateProfileRequest,
} from "@/features/profile/api/profile-api";
import type {
  Profile,
  UpdatePasswordPayload,
  UpdateProfilePayload,
} from "@/features/profile/model/types";

interface ProfileState {
  profile: Profile | null;
  isLoading: boolean;
  isSaving: boolean;
  isChangingPassword: boolean;
  error: string | null;
  saveError: string | null;
  saveSuccess: boolean;
  passwordError: string | null;
  passwordSuccess: boolean;

  loadProfile: () => Promise<void>;
  updateProfile: (payload: UpdateProfilePayload) => Promise<void>;
  updatePassword: (payload: UpdatePasswordPayload) => Promise<void>;
  clearFeedback: () => void;
  reset: () => void;
}

const initialState = {
  profile: null,
  isLoading: false,
  isSaving: false,
  isChangingPassword: false,
  error: null,
  saveError: null,
  saveSuccess: false,
  passwordError: null,
  passwordSuccess: false,
};

export const useProfileStore = create<ProfileState>((set) => ({
  ...initialState,

  loadProfile: async () => {
    set({ isLoading: true, error: null });
    try {
      const profile = await getProfile();
      set({ profile });
    } catch (error) {
      set({
        error: profileErrorMessage(error, "Error al cargar el perfil"),
      });
    } finally {
      set({ isLoading: false });
    }
  },

  updateProfile: async (payload) => {
    set({ isSaving: true, saveError: null, saveSuccess: false });
    try {
      const profile = await updateProfileRequest(payload);
      set({ profile, saveSuccess: true });
      useSessionStore.getState().setUser(profile);
    } catch (error) {
      set({
        saveError: profileErrorMessage(error, "Error al actualizar el perfil"),
      });
    } finally {
      set({ isSaving: false });
    }
  },

  updatePassword: async (payload) => {
    set({
      isChangingPassword: true,
      passwordError: null,
      passwordSuccess: false,
    });
    try {
      await updatePasswordRequest(payload);
      set({ passwordSuccess: true });
    } catch (error) {
      set({
        passwordError: profileErrorMessage(
          error,
          "Error al cambiar la contraseña"
        ),
      });
    } finally {
      set({ isChangingPassword: false });
    }
  },

  clearFeedback: () => {
    set({
      saveSuccess: false,
      saveError: null,
      passwordSuccess: false,
      passwordError: null,
    });
  },

  reset: () => set(initialState),
}));
