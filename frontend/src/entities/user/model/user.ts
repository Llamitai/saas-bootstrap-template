import type { RawEmailAddress } from "@/entities/user/model/email-address";
import type { RawPhoneNumber } from "@/entities/user/model/phone-number";

export interface User {
  uuid: string;
  username: string;
  firstName?: string | null;
  lastName?: string | null;
  phoneNumber?: RawPhoneNumber | null;
  emailAddress?: RawEmailAddress | null;
  photoUrl?: string | null;
  isSuperuser?: boolean;
}

export const emptyUser: User = {
  uuid: "",
  username: "",
};
