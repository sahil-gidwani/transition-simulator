import Badge from '../ui/Badge';
import Combobox from '../ui/Combobox';
import SkeletonBlock from '../ui/SkeletonBlock';
import { formatEuroCompact } from '../../lib/format';
import { clubBudgetLabel, tierLabel } from '../../lib/labels';
import type { DestinationClub, DestinationLeague } from '../../lib/types';

interface DestinationPickerProps {
  leagues: DestinationLeague[] | undefined;
  leagueId: string | null;
  clubId: number | null;
  onChange: (leagueId: string | null, clubId: number | null) => void;
}

export default function DestinationPicker({
  leagues,
  leagueId,
  clubId,
  onChange,
}: DestinationPickerProps) {
  if (!leagues) {
    return (
      <div
        role="status"
        aria-label="Loading destination leagues"
        className="glass-panel relative z-30 grid gap-4 rounded-xl p-4 sm:grid-cols-2"
      >
        <SkeletonBlock className="h-16 w-full" />
        <SkeletonBlock className="h-16 w-full" />
      </div>
    );
  }

  const selectedLeague = leagues.find((league) => league.league_id === leagueId) ?? null;
  const selectedClub = selectedLeague?.clubs.find((club) => club.club_id === clubId) ?? null;

  return (
    // z-30: the glass panel's backdrop-filter makes this a stacking context,
    // trapping the combobox dropdowns (z-10) inside it — without a raised
    // z-index the later-in-DOM verdict/narrative panels paint over them.
    <div className="glass-panel relative z-30 grid gap-4 rounded-xl p-4 sm:grid-cols-2">
      <Combobox<DestinationLeague>
        id="destination-league"
        label="Destination league"
        placeholder="Search leagues or countries…"
        items={leagues}
        itemKey={(league) => league.league_id}
        itemText={(league) => `${league.name} ${league.country ?? ''}`}
        renderItem={(league) => (
          <span className="flex items-center justify-between gap-3">
            <span className="min-w-0">
              <span className="block truncate text-ink-100">{league.name}</span>
              <span className="text-xs text-ink-400">
                {[
                  league.country,
                  league.median_squad_value_eur != null
                    ? `median squad ${formatEuroCompact(league.median_squad_value_eur)}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </span>
            <Badge title="League strength band from median squad value (Elite ≈ €100M+, Strong ≈ €24M+, Emerging ≈ €12M+, Developing below)">
              {tierLabel(league.tier)}
            </Badge>
          </span>
        )}
        selectedLabel={
          selectedLeague
            ? `${selectedLeague.name}${selectedLeague.country ? ` — ${selectedLeague.country}` : ''}`
            : null
        }
        onSelect={(league) => onChange(league.league_id, null)}
      />

      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <Combobox<DestinationClub>
            id="destination-club"
            label="Club (optional)"
            placeholder={selectedLeague ? 'Any club in the league' : 'Pick a league first'}
            items={selectedLeague?.clubs ?? []}
            itemKey={(club) => club.club_id}
            itemText={(club) => club.name}
            renderItem={(club) => (
              <span className="flex items-center justify-between gap-3">
                <span className="min-w-0">
                  <span className="block truncate text-ink-100">{club.name}</span>
                  <span className="text-xs text-ink-400">
                    {[
                      `squad ${formatEuroCompact(club.squad_value_eur)}`,
                      !club.elo_available ? 'no strength rating' : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
                {clubBudgetLabel(club.club_value_pct) ? (
                  <Badge title="Where this club's squad value sits within the league (the same signal the matching uses)">
                    {clubBudgetLabel(club.club_value_pct)}
                  </Badge>
                ) : null}
              </span>
            )}
            selectedLabel={selectedClub?.name ?? null}
            onSelect={(club) => onChange(leagueId, club.club_id)}
            disabled={!selectedLeague}
          />
        </div>
        {selectedClub ? (
          <button
            type="button"
            onClick={() => onChange(leagueId, null)}
            title="Any club in the league"
            aria-label="Clear club selection"
            className="rounded-lg border border-pitch-800 bg-pitch-900 px-3 py-2.5 text-sm text-ink-400 hover:border-yale-400"
          >
            ✕
          </button>
        ) : null}
      </div>
    </div>
  );
}
