-- Managed by the ai-sandbox 'lazyvim' role. Edits are overwritten on the next
-- playbook run.
--
-- Every plugin is installed by the role at the commit recorded in
-- lazy-lock.json, next to this config. Nothing here fetches code at runtime:
--   * lazy.nvim itself is cloned by the role at its locked commit. If it is
--     missing, this config refuses to clone an unpinned copy and says so.
--   * the update checker and config change detection are off.
--   * luarocks support is off, so no plugin can pull a rock.
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.api.nvim_echo({
    { "lazy.nvim is not installed at " .. lazypath .. ".\n", "ErrorMsg" },
    { "It is installed by the ai-sandbox 'lazyvim' role at a pinned commit. Re-run the playbook.", "WarningMsg" },
  }, true, {})
  return
end
vim.opt.rtp:prepend(lazypath)

-- The language extras come from lua/config/extras.lua, which the role
-- renders from its lazyvim_extras parameter (lang.go unless told otherwise). The core
-- spec is first and the developer's own lua/plugins/ last, so their specs
-- override both.
local spec = { { "LazyVim/LazyVim", import = "lazyvim.plugins" } }
local ok, extras = pcall(require, "config.extras")
vim.list_extend(spec, ok and extras or { { import = "lazyvim.plugins.extras.lang.go" } })
table.insert(spec, { import = "plugins" })

require("lazy").setup({
  spec = spec,
  defaults = {
    lazy = false,
    -- Resolve to commits, never to semver tags: the lockfile is the only
    -- source of which revision is installed.
    version = false,
  },
  install = { missing = true, colorscheme = { "tokyonight", "habamax" } },
  checker = { enabled = false },
  change_detection = { enabled = false },
  rocks = { enabled = false },
  performance = {
    rtp = {
      disabled_plugins = {
        "gzip",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
      },
    },
  },
})
