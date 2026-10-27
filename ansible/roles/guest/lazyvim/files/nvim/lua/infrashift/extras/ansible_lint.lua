-- Managed by the ai-sandbox 'lazyvim' role (extras=infrashift.ansible_lint).
--
-- ansible-lint diagnostics without a language server: no ansible-language-
-- server or yaml-language-server is installed (both are npm packages, and no
-- Node is installed for them). Playbooks, roles and task files get the compound
-- filetype `yaml.ansible`, nvim-lint runs `ansible-lint` (the 'ansible_tools'
-- role) on them, and they keep the YAML tree-sitter highlighting.
vim.filetype.add({
  pattern = {
    [".*/roles/.*/tasks/.*%.ya?ml"] = "yaml.ansible",
    [".*/roles/.*/handlers/.*%.ya?ml"] = "yaml.ansible",
    [".*/playbooks/.*%.ya?ml"] = "yaml.ansible",
    [".*/tasks/.*%.ya?ml"] = "yaml.ansible",
    [".*/site%.ya?ml"] = "yaml.ansible",
  },
})
vim.treesitter.language.register("yaml", "yaml.ansible")

return {
  {
    "mfussenegger/nvim-lint",
    opts = { linters_by_ft = { ["yaml.ansible"] = { "ansible_lint" } } },
  },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = { ensure_installed = { "yaml" } },
  },
}
