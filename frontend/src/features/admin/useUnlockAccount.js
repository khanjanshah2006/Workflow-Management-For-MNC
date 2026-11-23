import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";

/**
 * Unlock mutation shared by the user table and the anomaly alerts banner (US-48).
 * POST /api/v1/admin/users/{account_id}/unlock, then refetch users and alerts.
 * A 409 ("Account is not locked") is reported and the lists are refetched too.
 *
 * @param {(type: "success" | "error", message: string) => void} notify
 */
export function useUnlockAccount(notify) {
  const queryClient = useQueryClient();

  const refetchLists = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
      queryClient.invalidateQueries({ queryKey: ["admin", "anomaly-alerts"] }),
    ]);

  return useMutation({
    mutationFn: ({ accountId }) => adminApi.unlockAccount(accountId),
    onSuccess: (data, { email }) => {
      notify("success", `${data?.email || email || "Account"} has been unlocked.`);
      return refetchLists();
    },
    onError: (err) => {
      if (err?.status === 409) {
        notify("error", err.message || "Account is not locked.");
        return refetchLists();
      }
      notify("error", err?.message || "Failed to unlock account.");
      return undefined;
    },
  });
}

export default useUnlockAccount;
