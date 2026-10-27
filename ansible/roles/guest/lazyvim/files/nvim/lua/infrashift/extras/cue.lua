-- Managed by the ai-sandbox 'lazyvim' role (extras=infrashift.cue).
--
-- LazyVim has no CUE extra. This is the whole of one: the tree-sitter parser,
-- and `cue lsp` -- the language server built into the cue CLI the trusted
-- 'cuelang' feature installs -- attached to *.cue buffers.
return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "cue" } },
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        cue = {
          mason = false,
          cmd = { "cue", "lsp" },
          filetypes = { "cue" },
          root_markers = { "cue.mod", ".git" },
        },
      },
    },
  },
}
