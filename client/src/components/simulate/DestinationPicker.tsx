import Badge from '../ui/Badge';
import Combobox from '../ui/Combobox';
import SkeletonBlock from '../ui/SkeletonBlock';
import { tercileLabel, tierLabel } from '../../lib/labels';
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
        className="grid gap-4 rounded-xl border border-pitch-800 bg-pitch-900/60 p-4 sm:grid-cols-2"
      >
        <SkeletonBlock className="h-16 w-full" />
        <SkeletonBlock className="h-16 w-full" />
      </div>
    );
  }

  const selectedLeague = leagues.find((league) => league.league_id === leagueId) ?? null;
  const selectedClub = selectedLeague?.clubs.find((club) => club.club_id === clubId) ?? null;

  return (
    <div className="grid gap-4 rounded-xl border border-pitch-800 bg-pitch-900/60 p-4 sm:grid-cols-2">
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
              {league.country ? (
                <span className="text-xs text-ink-400">{league.country}</span>
              ) : null}
            </span>
            <Badge>{tierLabel(league.tier)}</Badge>
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
                <span className="truncate text-ink-100">{club.name}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {tercileLabel(club.tercile) ? <Badge>{tercileLabel(club.tercile)}</Badge> : null}
                  {!club.elo_available ? (
                    <span className="text-xs text-ink-400">no Elo</span>
                  ) : null}
                </span>
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
            className="rounded-lg border border-pitch-800 bg-pitch-900 px-3 py-2.5 text-sm text-ink-400 hover:border-brass-400"
          >
            ✕
          </button>
        ) : null}
      </div>
    </div>
  );
}
