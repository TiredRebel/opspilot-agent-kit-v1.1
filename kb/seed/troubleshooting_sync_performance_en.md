# Troubleshooting: Sync & Performance

This guide covers the most common sync issue with the Acme Cloud Suite desktop app, plus general
tips for keeping the app fast and responsive.

## Desktop app stuck "syncing"

The most common sync problem is the desktop app appearing to hang with a perpetual "Syncing..."
indicator that never completes. This almost always happens when the app's **local cache exceeds
2GB**. Once the local cache grows past that size, the sync process can get stuck trying to
reconcile a large amount of local data against the cloud.

**Fix:** Clear the local cache.

1. Open the Acme Cloud Suite desktop app.
2. Go to **Settings > Storage > Clear Cache**.
3. Confirm the action.

Clearing the local cache **does not delete any cloud data** — it only removes the local copy
stored on your device. After clearing the cache, the app will re-download the data it needs from
the cloud and resume syncing normally. This is safe to do at any time and does not affect your
projects, tasks, or files stored in Acme Cloud Suite's cloud storage.

If you regularly work with large projects or attachments, consider checking
**Settings > Storage** periodically to see how large your local cache has grown, so you can clear
it proactively before it reaches 2GB and triggers a stuck sync.

## General performance tips

- **Keep the desktop app updated.** Performance improvements and sync fixes ship in regular
  updates; check **Help > Check for Updates** if the app feels sluggish.
- **Clear the local cache periodically** (Settings > Storage > Clear Cache), especially on
  machines with limited disk space, since a large cache is the most common cause of slow or
  stuck syncing.
- **Close unused projects/boards** if you're a member of many workspaces — the desktop app
  syncs data for all projects you have access to, and trimming what's open locally can reduce
  load.
- **Check your network connection.** Slow or unstable connections can make sync appear stuck
  even when the local cache is small; try switching networks or restarting your router if sync
  is consistently slow.
- **Restart the app** after a large import or bulk operation (for example, importing hundreds of
  tasks at once) to let it fully reindex your local cache.
- **Browser performance:** if you use the web app instead of the desktop app and notice slowness,
  clearing your browser cache and disabling browser extensions that inject content into web
  pages can also help.

## Still slow after clearing the cache?

If clearing the local cache doesn't resolve stuck syncing or continued slowness, contact support
with details about your operating system, app version, and roughly how large your workspace is
(number of projects and users). Response times follow your plan's support SLA: 48 hours for Free
and Starter, 24 hours for Pro, and 4 hours for Enterprise.
