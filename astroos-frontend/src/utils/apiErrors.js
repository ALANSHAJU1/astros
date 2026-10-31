export function getApiErrorMessage(error, fallback = "Request failed.") {
  if (!error) return fallback;

  if (error.code === "ERR_NETWORK" || error.message === "Network Error") {
    return "Cannot reach the AstroOS backend. Confirm it is running and that CORS allows this origin.";
  }

  if (error.code === "ECONNABORTED") {
    return "The request timed out. The astronomy engine may still be processing this session.";
  }

  const detail = error.response?.data?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item?.msg) {
          const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
          return location ? `${location}: ${item.msg}` : item.msg;
        }
        return null;
      })
      .filter(Boolean);

    if (messages.length) return messages.join(" ");
  }

  if (error.response?.status === 401) {
    return "Your session is not authorized. Sign in again to continue.";
  }

  if (error.response?.status === 403) {
    return "You do not have permission to use this feature.";
  }

  if (error.response?.status === 422) {
    return "The request did not pass validation. Check the submitted fields and try again.";
  }

  return error.message || fallback;
}
