"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Star, Trash2, Search, RefreshCw } from "lucide-react";

export default function AdminReviews() {
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get("/metrics/ratings");
      setReviews(res || []);
    } catch (err: any) {
      setError("Failed to fetch reviews");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this review?")) return;
    try {
      await api.delete("/api/admin/ratings/" + id);
      setReviews(reviews.filter((r) => r.id !== id));
    } catch (err: any) {
      alert("Failed to delete review");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-display font-bold flex items-center gap-2">
          <Star className="text-primary-400" />
          Reviews Management
        </h1>
        <button
          onClick={fetchReviews}
          className={"flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors"}
        >
          <RefreshCw className={loading ? "w-4 h-4 animate-spin" : "w-4 h-4"} />
          Refresh
        </button>
      </div>

      {error ? (
        <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-500">
          {error}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {reviews.map((review) => (
            <motion.div
              key={review.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6 flex flex-col justify-between"
            >
              <div>
                <div className="flex justify-between items-start mb-4">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <Star
                        key={star}
                        className={star <= review.rating ? "w-5 h-5 fill-primary-400 text-primary-400" : "w-5 h-5 text-gray-600"}
                      />
                    ))}
                  </div>
                  <span className="text-xs px-2 py-1 bg-white/5 rounded-full capitalize text-gray-400">
                    {review.source}
                  </span>
                </div>
                {review.comment ? (
                  <p className="text-sm text-gray-300 mb-4 whitespace-pre-wrap">
                    "{review.comment}"
                  </p>
                ) : (
                  <p className="text-sm text-gray-500 italic mb-4">
                    No comment provided
                  </p>
                )}
              </div>

              <div className="flex justify-between items-end border-t border-white/10 pt-4 mt-auto">
                <div className="text-xs text-gray-500 space-y-1">
                  <div className="truncate max-w-[150px]">
                    {review.user_name || review.user_email || "Anonymous"}
                  </div>
                  <div>
                    {new Date(review.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(review.id)}
                  className="p-2 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Delete Review"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </motion.div>
          ))}
          {!loading && reviews.length === 0 && (
            <div className="col-span-full py-12 text-center text-gray-500 bg-white/5 rounded-xl border border-white/10 relative">
              No reviews found!
            </div>
          )}
        </div>
      )}
    </div>
  );
}
