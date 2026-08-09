import { useEffect, useState } from "react";

const KEY = "hmrec.profileId";

export function useProfileId() {
  const [profileId, setProfileId] = useState<string | null>(() =>
    localStorage.getItem(KEY)
  );

  useEffect(() => {
    if (profileId) localStorage.setItem(KEY, profileId);
    else localStorage.removeItem(KEY);
  }, [profileId]);

  return { profileId, setProfileId };
}
