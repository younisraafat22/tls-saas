with open("frontend/src/app/admin/page.tsx", "r", encoding="utf-8") as f:
    text = f.read()

old_grid = 'className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4"'
new_grid = 'className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4"'
text = text.replace(old_grid, new_grid)

old_cards = """        <StatCard
          icon={<Clock className="w-5 h-5" />}
          iconColor="text-amber-400"
          label="Pending Licenses"
          value={stats?.pending_licenses ?? "—"}
          href="/admin/licenses"
        />
      </motion.div>"""

new_cards = """        <StatCard
          icon={<Clock className="w-5 h-5" />}
          iconColor="text-amber-400"
          label="Pending Licenses"
          value={stats?.pending_licenses ?? "—"}
          href="/admin/licenses"
        />
        <StatCard
          icon={<Download className="w-5 h-5" />}
          iconColor="text-purple-400"
          label="App Downloads"
          value={stats?.total_downloads ?? 0}
        />
        <StatCard
          icon={<Star className="w-5 h-5" />}
          iconColor="text-yellow-400"
          label="Avg Rating"
          value={stats?.average_rating ? stats.average_rating.toFixed(1) : "0.0"}
        />
        <StatCard
          icon={<Trophy className="w-5 h-5" />}
          iconColor="text-teal-400"
          label="Appt. Found"
          value={stats?.total_appointments_found ?? 0}
        />
      </motion.div>"""

text = text.replace(old_cards, new_cards)

# Also need to import Download, Star, Trophy
if "Download," not in text and "lucide-react" in text:
    text = text.replace(', Users } from "lucide-react";', ', Users, Download, Star, Trophy } from "lucide-react";')

with open("frontend/src/app/admin/page.tsx", "w", encoding="utf-8") as f:
    f.write(text)
print("done frontend admin page")
