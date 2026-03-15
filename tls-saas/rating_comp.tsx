// -- Rating ----------------------------------------------

function RatingComponent() {
  const { t } = useLanguage();
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0) return;
    setSubmitting(true);
    try {
      await fetch((process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000") + "/metrics/rate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment, source: "website" }),
      });
      setSubmitted(true);
    } catch (err) {
      console.error(err);
    }
    setSubmitting(false);
  };

  if (submitted) {
    return (
      <section id="rating" className="py-24 relative overflow-hidden">
        <div className="max-w-2xl mx-auto px-4 text-center">
          <motion.div variants={scaleIn} initial="hidden" animate="visible" className="glass-card p-12 rounded-2xl border border-primary-500/20 bg-primary-500/5">
            <Check className="w-16 h-16 text-primary-400 mx-auto mb-6" />
            <h3 className="text-3xl font-display font-bold text-white mb-4">{t.rating?.thanks ?? "Thank you for your feedback!"}</h3>
          </motion.div>
        </div>
      </section>
    );
  }

  return (
    <section id="rating" className="py-24 relative overflow-hidden">
      <div className="max-w-2xl mx-auto px-4">
        <AnimatedSection className="glass-card p-8 md:p-12 rounded-2xl border border-white/10 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary-500/10 via-transparent to-transparent pointer-events-none" />
          <div className="text-center mb-8">
            <h2 className="text-3xl font-display font-bold text-white mb-3">{t.rating?.title ?? "Rate Your Experience"}</h2>
            <p className="text-gray-400">{t.rating?.sub ?? "Let us know how the service works for you!"}</p>
          </div>
          
          <div className="flex justify-center gap-2 mb-8">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                className="focus:outline-none transition-transform hover:scale-110"
                onMouseEnter={() => setHovered(star)}
                onMouseLeave={() => setHovered(0)}
                onClick={() => setRating(star)}
              >
                <Star
                  className={"" + "w-10 h-10 transition-colors " + ((hovered || rating) >= star ? "fill-primary-400 text-primary-400" : "text-gray-600")}
                />
              </button>
            ))}
          </div>

          <div className="space-y-4">
            <textarea
              className="w-full bg-dark-800/50 border border-white/10 rounded-xl p-4 text-white placeholder:text-gray-500 focus:outline-none focus:border-primary-500/50 transition-colors resize-none"
              rows={3}
              placeholder={t.rating?.placeholder ?? "Optional feedback..."}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <button
              onClick={handleSubmit}
              disabled={submitting || rating === 0}
              className="w-full btn-gradient py-4 rounded-xl font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {submitting ? "..." : (t.rating?.submit ?? "Submit Rating")}
            </button>
          </div>
        </AnimatedSection>
      </div>
    </section>
  );
}

