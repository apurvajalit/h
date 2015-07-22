'use strict';

/**
 * @ngdoc directive
 * @name groupList
 * @restrict AE
 * @description Displays a list of groups of which the user is a member.
 */
module.exports = function () {
  return {
    restrict: 'AE',
    templateUrl: 'group_list.html'
  };
};
