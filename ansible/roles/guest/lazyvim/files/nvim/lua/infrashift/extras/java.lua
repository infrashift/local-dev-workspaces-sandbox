-- Managed by the ai-sandbox 'lazyvim' role (extras=lang.java).
--
-- LazyVim's java extra starts jdtls as `exepath("jdtls")` and, because
-- mason.nvim is in the spec, appends -javaagent:$MASON/share/jdtls/lombok.jar
-- -- a file that does not exist here, since Mason installs nothing (see
-- lua/plugins/offline.lua). jdtls would then refuse to start. The 'java-tools'
-- feature installs jdtls and lombok under ~/.local and its `jdtls` launcher
-- adds the lombok agent itself, so the command is just the launcher.
return {
  {
    "mfussenegger/nvim-jdtls",
    opts = function(_, opts)
      opts.cmd = { vim.fn.exepath("jdtls") }
    end,
  },
}
