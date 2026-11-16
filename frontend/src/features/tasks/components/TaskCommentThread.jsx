import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTaskComments,
  createTaskComment,
  validateCommentContent,
  MAX_COMMENT_LENGTH,
} from "../../../api/tasksApi";
import { useAuth } from "../../../context/AuthContext";

/**
 * Format timestamp into human-friendly relative or calendar time.
 * @param {string} isoString
 * @returns {string}
 */
function formatCommentTime(isoString) {
  if (!isoString) return "Just now";
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return "Recently";
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "Recently";
  }
}

/**
 * Derive avatar initials from a user's full name.
 * @param {string} name
 * @returns {string}
 */
function getInitials(name) {
  if (!name || typeof name !== "string") return "U";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }
  return parts[0].slice(0, 2).toUpperCase();
}

/**
 * TaskCommentThread Component (US-33)
 *
 * Reusable threaded discussion feed embedded in TaskDetailDrawer and review modals:
 * - Chronological discussion list with avatars, author names, role tags, and timestamps
 * - Optimistic UI updates when posting new messages
 * - Live character counter (max 2,000 characters)
 * - Auto-scroll to latest message on render and upon posting
 * - Keyboard shortcut (Ctrl+Enter / Cmd+Enter) to submit
 *
 * @param {Object} props
 * @param {number|string} props.taskId Active task ID
 * @param {Object} [props.currentUser] Optional authenticated user object override
 */
export default function TaskCommentThread({ taskId, currentUser: propUser }) {
  const queryClient = useQueryClient();
  const { user: authUser, role: authRole } = useAuth();
  const currentUser = propUser || authUser || {};

  const [commentText, setCommentText] = useState("");
  const [errorMessage, setErrorMessage] = useState(null);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Fetch comments with cache sharing across drawer and modals
  const {
    data: comments = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["tasks", taskId, "comments"],
    queryFn: () => getTaskComments(taskId),
    enabled: Boolean(taskId),
    staleTime: 10000,
  });

  // Auto-scroll to bottom whenever comments length changes
  useEffect(() => {
    if (comments.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [comments.length]);

  // Optimistic Mutation
  const postCommentMutation = useMutation({
    mutationFn: (content) => createTaskComment(taskId, content),
    onMutate: async (newContent) => {
      setErrorMessage(null);
      // Cancel any outgoing refetches so they don't overwrite optimistic update
      await queryClient.cancelQueries({ queryKey: ["tasks", taskId, "comments"] });

      // Snapshot previous comments
      const previousComments =
        queryClient.getQueryData(["tasks", taskId, "comments"]) || [];

      // Optimistic comment object
      const optimisticComment = {
        comment_id: `temp-${Date.now()}`,
        task_id: Number(taskId),
        author_name: currentUser.full_name || currentUser.name || currentUser.email || "You",
        author_role: currentUser.role || authRole || "Team Member",
        content: newContent.trim(),
        created_at: new Date().toISOString(),
        isOptimistic: true,
      };

      // Optimistically update query cache
      queryClient.setQueryData(
        ["tasks", taskId, "comments"],
        [...previousComments, optimisticComment]
      );

      // Clear input immediately for snappy UX
      setCommentText("");

      return { previousComments };
    },
    onError: (err, newContent, context) => {
      // Rollback to previous state on failure
      if (context?.previousComments) {
        queryClient.setQueryData(
          ["tasks", taskId, "comments"],
          context.previousComments
        );
      }
      setErrorMessage(
        err?.message || "Failed to post comment. Please try again."
      );
      // Restore input text so user does not lose their typed message
      setCommentText(newContent);
    },
    onSettled: () => {
      // Always refetch after error or success to guarantee sync with server
      queryClient.invalidateQueries({ queryKey: ["tasks", taskId, "comments"] });
    },
  });

  const charCount = commentText.length;
  const isOverLimit = charCount > MAX_COMMENT_LENGTH;
  const isSubmitDisabled =
    !commentText.trim() || isOverLimit || postCommentMutation.isPending;

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (isSubmitDisabled) return;

    const check = validateCommentContent(commentText);
    if (!check.valid) {
      setErrorMessage(check.error);
      return;
    }

    postCommentMutation.mutate(check.trimmed);
  };

  const handleKeyDown = (e) => {
    // Submit on Ctrl+Enter or Cmd+Enter
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="task-comment-thread" aria-label="Task comments thread">
      {/* Header */}
      <div className="comment-thread-header">
        <h4 className="comment-thread-title">
          <span aria-hidden="true">💬</span> Discussion ({comments.length})
        </h4>
        <span className="comment-thread-badge">Chronological Thread</span>
      </div>

      {/* Error alert banner */}
      {errorMessage && (
        <div className="alert-banner alert-banner-danger" role="alert">
          <span className="alert-icon">⚠️</span>
          <span className="alert-text">{errorMessage}</span>
          <button
            type="button"
            className="alert-close-btn"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && comments.length === 0 && (
        <div className="comment-loading-state" role="status">
          <div className="spinner-border spinner-border-sm" />
          <span>Loading comments...</span>
        </div>
      )}

      {/* Query Error state */}
      {isError && (
        <div className="comment-error-state" role="alert">
          <span>Failed to load discussion thread: {error?.message}</span>
          <button
            type="button"
            className="btn btn-secondary btn-xs"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && comments.length === 0 && (
        <div className="comment-empty-state">
          <span className="empty-bubble-icon" aria-hidden="true">💭</span>
          <p className="empty-title">No comments yet</p>
          <p className="empty-subtext">
            Start the conversation by sharing notes, blockers, or deliverables feedback with your team.
          </p>
        </div>
      )}

      {/* Comments List Feed */}
      <div className="comment-feed-list" role="feed" aria-busy={postCommentMutation.isPending}>
        {comments.map((comment) => {
          const initials = getInitials(comment.author_name);
          const timeFormatted = formatCommentTime(comment.created_at);

          return (
            <article
              key={comment.comment_id}
              className={`comment-bubble-item ${
                comment.isOptimistic ? "comment-item-optimistic" : ""
              }`}
              aria-label={`Comment by ${comment.author_name}`}
            >
              <div className="comment-author-avatar" title={comment.author_name} aria-hidden="true">
                {initials}
              </div>

              <div className="comment-content-wrapper">
                <header className="comment-metadata">
                  <span className="comment-author-name">{comment.author_name}</span>
                  {comment.author_role && (
                    <span className="comment-role-tag">{comment.author_role}</span>
                  )}
                  <time className="comment-timestamp" dateTime={comment.created_at}>
                    {timeFormatted}
                  </time>
                  {comment.isOptimistic && (
                    <span className="comment-optimistic-tag" title="Sending message to server...">
                      Sending...
                    </span>
                  )}
                </header>

                <div className="comment-body-text">{comment.content}</div>
              </div>
            </article>
          );
        })}
        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {/* Input Box with Live Character Counter */}
      <form onSubmit={handleSubmit} className="comment-input-form">
        <div className="comment-textarea-wrap">
          <textarea
            ref={textareaRef}
            className={`comment-textarea ${isOverLimit ? "textarea-limit-exceeded" : ""}`}
            rows={2}
            placeholder="Write a comment... (Ctrl+Enter to post)"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={postCommentMutation.isPending}
            aria-label="Write a comment"
            aria-describedby="comment-char-counter"
          />
        </div>

        <div className="comment-form-actions">
          <span
            id="comment-char-counter"
            className={`comment-char-counter ${
              isOverLimit
                ? "counter-exceeded"
                : charCount > 1800
                ? "counter-warning"
                : ""
            }`}
          >
            {charCount.toLocaleString()} / {MAX_COMMENT_LENGTH.toLocaleString()}
          </span>

          <button
            type="submit"
            className="btn btn-primary btn-sm btn-post-comment"
            disabled={isSubmitDisabled}
          >
            {postCommentMutation.isPending ? "Posting..." : "Post Comment"}
          </button>
        </div>
      </form>
    </div>
  );
}
